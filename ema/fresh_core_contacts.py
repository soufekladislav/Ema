"""Company-scoped, bounded Fresh Core contact sync. No parallel CRM store."""
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

from cryptography.fernet import InvalidToken
from sqlalchemy import func, select

from .mail_service import decrypt_password, validate_mail_host, MailError
from .models import Company, Contact, ContactOrigin, FreshCoreSource, now


class FreshCoreError(Exception):
    pass


def canonical_site(value):
    """Only approved HTTPS WordPress origins, never private-network URLs."""
    raw = (value or "").strip()
    parts = urllib.parse.urlsplit(raw)
    try:
        port = parts.port
    except ValueError:
        raise FreshCoreError("Neplatný port HTTPS webu.") from None
    if (parts.scheme.lower() != "https" or not parts.hostname or
            parts.username or parts.password or parts.query or parts.fragment or
            port not in (None, 443)):
        raise FreshCoreError("Zadejte HTTPS adresu webu bez parametrů a přihlašovacích údajů.")
    try:
        validate_mail_host(parts.hostname)
    except MailError as ex:
        raise FreshCoreError("Web musí být dostupný na veřejné HTTPS adrese.") from ex
    path = parts.path.rstrip("/")
    if ".." in path or "//" in path or len(path) > 90:
        raise FreshCoreError("Neplatná cesta WordPress webu.")
    url = "https://" + parts.hostname.lower() + path
    if len(url) > 240:
        raise FreshCoreError("Příliš dlouhá adresa WordPress webu.")
    return url


def _check_advertised_site(configured_site, advertised_site):
    """Check WP home_url identity, allowing only a same-site www alias.

    The response has already arrived over verified HTTPS from configured_site,
    with redirects disabled. WordPress home_url may be configured as http
    behind a TLS proxy or with/without www; it is only metadata, never a
    destination for a second credential-bearing request.
    """
    remote = urllib.parse.urlsplit(str(advertised_site or ""))
    local = urllib.parse.urlsplit(configured_site)
    try:
        port = remote.port
    except ValueError:
        port = -1
    if (remote.scheme not in ("https", "http") or not remote.hostname or
            remote.username or remote.password or remote.query or remote.fragment or
            port not in (None, 80, 443)):
        raise FreshCoreError("Fresh Core vrátil neplatnou adresu zdrojového webu.")
    def canonical_host(host):
        name = host.lower().rstrip(".")
        return name[4:] if name.startswith("www.") else name
    if canonical_host(remote.hostname) != canonical_host(local.hostname):
        raise FreshCoreError(
            "Fresh Core hlásí jinou doménu než připojený web. "
            "Ověřte doménu ve WordPress nastavení."
        )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_page(source, key, kind, *, after=0, limit=50):
    """Remote read only. Never follow redirects or spill the credential to logs."""
    if kind not in ("users", "elementor_submissions") or not 0 <= after <= 2_147_483_647:
        raise FreshCoreError("Neplatný typ nebo stránkování kontaktů.")
    site = canonical_site(source.site_url)
    try:
        password = decrypt_password(source.credential, key)
    except (MailError, InvalidToken, ValueError, UnicodeError) as ex:
        raise FreshCoreError("Přístupový klíč konektoru nelze rozšifrovat.") from ex
    url = site + "/wp-json/fresh-core/v1/accounting/contacts?" + urllib.parse.urlencode({
        "kind": kind, "after_id": after, "limit": min(50, max(1, limit))
    })
    req = urllib.request.Request(url, headers={
        "X-Fresh-Core-Accounting-Key": password,
        "Accept": "application/json",
        "User-Agent": "EMA-Fresh-Core-CRM/1",
    })
    try:
        with urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=ssl.create_default_context())).open(req, timeout=12) as r:
            data = r.read(262145)
            if len(data) > 262144:
                raise FreshCoreError("Odpověď Fresh Core přesahuje povolenou velikost.")
    except urllib.error.HTTPError as ex:
        if ex.code in (301, 302, 303, 307, 308):
            raise FreshCoreError(
                "WordPress přesměroval požadavek. Připojte jeho výslednou HTTPS adresu "
                "(např. správnou variantu www); klíč se nikam nepřeposílal."
            ) from None
        if ex.code in (401, 403):
            raise FreshCoreError("Fresh Core odmítl účetní READ klíč nebo přístup.") from None
        if ex.code == 404:
            raise FreshCoreError("Fresh Core na webu nemá kontaktní API – aktualizujte plugin.") from None
        raise FreshCoreError("Fresh Core vrátil chybu HTTP " + str(ex.code) + ".") from None
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        raise FreshCoreError("Nelze bezpečně načíst kontakty z webu. Ověřte HTTPS a připojení.") from None
    try:
        payload = json.loads(data)
    except (ValueError, TypeError, UnicodeError):
        raise FreshCoreError(
            "Fresh Core nevrátil JSON. Ověřte, zda endpoint nepřepisuje "
            "cache, firewall nebo přihlašovací stránka WordPressu."
        ) from None
    if not isinstance(payload, dict):
        raise FreshCoreError("Fresh Core vrátil JSON v neočekávaném formátu.")
    if payload.get("ok") is not True:
        raise FreshCoreError("Fresh Core neohlásil úspěšné načtení kontaktů.")
    if payload.get("kind") != kind:
        raise FreshCoreError("Fresh Core vrátil jiný typ zdroje kontaktů.")
    if type(payload.get("available")) is not bool:
        raise FreshCoreError("Fresh Core neuvedl dostupnost zdroje kontaktů.")
    if (not isinstance(payload.get("items"), list) or
            len(payload["items"]) > limit or type(payload.get("has_more")) is not bool):
        raise FreshCoreError("Fresh Core vrátil neplatné stránkování kontaktů.")
    _check_advertised_site(site, payload.get("site"))
    cursor = payload.get("next_after_id")
    if type(cursor) is not int or cursor < after or (payload["has_more"] and cursor <= after):
        raise FreshCoreError("Fresh Core vrátil neplatný kurzor kontaktů.")
    if any(not isinstance(item, dict) or type(item.get("source_id")) is not int
           for item in payload["items"]):
        raise FreshCoreError("Fresh Core vrátil neplatný identifikátor kontaktu.")
    return payload

def ingest_contacts(db, organization_id, site, kind, rows):
    """Merge provenance, not whole customers. Caller owns transaction and cursor."""
    created = linked = skipped = 0
    for item in rows:
        sid = item.get("source_id")
        if type(sid) is not int or sid < 1:
            raise FreshCoreError("Neplatný identifikátor zdrojového kontaktu.")
        if item.get("skip"):
            skipped += 1
            continue
        email = str(item.get("email") or "").strip().lower()
        if len(email) > 190 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            skipped += 1
            continue
        source_id = str(sid)
        origin = db.scalar(select(ContactOrigin).where(
            ContactOrigin.organization_id == organization_id,
            ContactOrigin.source_site == site,
            ContactOrigin.source_kind == kind,
            ContactOrigin.external_id == source_id,
        ))
        if origin:
            origin.last_seen_at = now()
            linked += 1
            continue
        contact = db.scalar(select(Contact).where(
            Contact.organization_id == organization_id, func.lower(Contact.email) == email
        ).order_by(Contact.id).limit(1))
        if not contact:
            company_id = None
            company_name = str(item.get("company") or "").strip()[:190]
            if company_name:
                company = db.scalar(select(Company).where(
                    Company.organization_id == organization_id,
                    func.lower(Company.name) == company_name.lower()
                ).limit(1))
                if not company:
                    company = Company(organization_id=organization_id, name=company_name)
                    db.add(company)
                    db.flush()
                company_id = company.id
            name = str(item.get("name") or "").strip()[:190] or email
            phone = str(item.get("phone") or "").strip()[:60]
            contact = Contact(
                organization_id=organization_id, company_id=company_id,
                email=email, name=name, phone=phone,
                metadata_json=json.dumps({"import_source": kind, "marketing_permission": "unverified"}, ensure_ascii=False)
            )
            db.add(contact)
            db.flush()
            created += 1
        else:
            linked += 1
        db.add(ContactOrigin(
            organization_id=organization_id, contact_id=contact.id,
            source_site=site, source_kind=kind, external_id=source_id,
        ))
    return {"created": created, "linked": linked, "skipped": skipped}


def update_csv_origin(db, contact, label, external_id=None):
    """Record CSV provenance including rows which don't have an email."""
    source = "CSV: " + (label.strip()[:170] or "Import")
    external_id = external_id or contact.email.lower()
    origin = db.scalar(select(ContactOrigin).where(
        ContactOrigin.organization_id == contact.organization_id,
        ContactOrigin.source_site == source,
        ContactOrigin.source_kind == "csv",
        ContactOrigin.external_id == external_id,
    ))
    if origin:
        origin.last_seen_at = now()
    else:
        db.add(ContactOrigin(
            organization_id=contact.organization_id, contact_id=contact.id,
            source_site=source, source_kind="csv", external_id=external_id
        ))


def synchronize_source(db, source, key, max_pages=3):
    """One atomic, bounded batch. Shared by the UI action and Exon cron."""
    totals = {"created": 0, "linked": 0, "skipped": 0}
    pending = False
    for kind, attr in (("users", "users_after_id"),
                       ("elementor_submissions", "forms_after_id")):
        for _ in range(max_pages):
            cursor = getattr(source, attr)
            result = fetch_page(source, key, kind, after=cursor, limit=50)
            if not result["available"]:
                setattr(source, attr, 0)
                break
            stats = ingest_contacts(db, source.organization_id, source.site_url,
                                    kind, result["items"])
            for k in totals:
                totals[k] += stats[k]
            # Cursor progresses only within the transaction. Any subsequent
            # API error means the whole batch is rolled back by the caller.
            setattr(source, attr, result["next_after_id"] if result["has_more"] else 0)
            if not result["has_more"]:
                break
        pending |= getattr(source, attr) > 0
    source.last_synced_at = now()
    source.last_error = ""
    return totals, pending
