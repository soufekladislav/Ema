"""Small IMAP/SMTP adapter. Never mirrors MIME bodies or attachments in the DB."""
import email
import imaplib
import ipaddress
import re
import smtplib
import socket
import ssl
from email.utils import getaddresses, make_msgid, formatdate
from pathlib import PurePath
from datetime import timezone
from email.headerregistry import Address
from email.message import EmailMessage
from email.parser import BytesHeaderParser
from email.policy import default
from email.utils import parsedate_to_datetime
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from .models import MailFolder, MailMessage, now
from .mail_render import make_preview, MAX_PREVIEW_BYTES


class MailError(Exception):
    pass


def validate_mail_host(host):
    """Fail closed for localhost/private IP DNS; only externally routable endpoints."""
    host = (host or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,188}", host) or host.endswith("."):
        raise MailError("Neplatný název poštovního serveru")
    if host in ("localhost",) or host.endswith((".local", ".internal")):
        raise MailError("Lokální poštovní server není povolen")
    try:
        addresses = {ipaddress.ip_address(a[4][0]) for a in socket.getaddrinfo(host, None)}
    except (socket.gaierror, ValueError, OSError) as ex:
        raise MailError("Poštovní server není dostupný v DNS") from ex
    if not addresses or any(not address.is_global for address in addresses):
        raise MailError("Pro připojení je nutná veřejná IP adresa")
    return host


def quote_mailbox_name(name):
    """imaplib does not quote folder arguments; preserve modified UTF-7 safely."""
    if not isinstance(name, str) or not name or len(name) > 190 or any(
        char in name for char in ("\r", "\n", "\x00")
    ):
        raise MailError("Neplatná IMAP složka")
    try:
        name.encode("ascii")
    except UnicodeEncodeError:
        raise MailError("IMAP složka není v serverovém kódování") from None
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


def encrypt_password(password, key):
    if not key:
        raise MailError("Chybí MAIL_ENCRYPTION_KEY")
    return Fernet(key.encode("ascii")).encrypt(password.encode()).decode("ascii")


def decrypt_password(ciphertext, key):
    if not key:
        raise MailError("Chybí MAIL_ENCRYPTION_KEY")
    return Fernet(key.encode("ascii")).decrypt(ciphertext.encode()).decode()


def _connect(box, key):
    """Connect safely and map connection/authentication failures to actionable user messages."""
    validate_mail_host(box.imap_host)
    try:
        password = decrypt_password(box.credential, key)
    except (InvalidToken, ValueError, UnicodeError):
        raise MailError("Uložené heslo schránky nelze rozšifrovat. Ověřte původní MAIL_ENCRYPTION_KEY; klíč neměňte naslepo.") from None
    try:
        client = imaplib.IMAP4_SSL(box.imap_host, box.imap_port, ssl_context=ssl.create_default_context(), timeout=18)
    except ssl.SSLError:
        raise MailError("IMAP TLS certifikát nebo zabezpečené spojení není v pořádku.") from None
    except (OSError, TimeoutError):
        raise MailError("Nelze navázat spojení s IMAP serverem (port 993). Zkontrolujte hostitele a dostupnost z Exonu.") from None
    try:
        client.login(box.username, password)
        return client
    except (imaplib.IMAP4.error, ssl.SSLError, OSError, TimeoutError) as ex:
        try:
            client.logout()
        except Exception:
            pass
        if isinstance(ex, imaplib.IMAP4.error):
            raise MailError("IMAP server odmítl přihlášení. Ověřte IMAP login, heslo a případné aplikační heslo.") from None
        if isinstance(ex, ssl.SSLError):
            raise MailError("Při IMAP přihlášení selhalo zabezpečené spojení TLS.") from None
        raise MailError("Spojení s IMAP serverem se během přihlášení přerušilo.") from None


def parse_metadata(raw, uid, box_id, folder_id, uidvalidity):
    """Only header bytes (not MIME bodies) are ever passed here."""
    pieces = [p for p in raw if isinstance(p, tuple) and len(p) > 1]
    if not pieces:
        raise MailError("IMAP nevrátil hlavičku zprávy")
    raw_info = pieces[0][0].decode("ascii", "replace")
    header = BytesHeaderParser(policy=default).parsebytes(pieces[0][1])
    size_match = re.search(r"RFC822.SIZE\s+(\d+)", raw_info, re.I)
    flag_match = re.search(r"FLAGS\s+\(([^)]*)\)", raw_info, re.I)
    try:
        dt = parsedate_to_datetime(str(header.get("Date", "")))
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, TypeError, OverflowError):
        dt = None
    return MailMessage(
        mailbox_id=box_id, folder_id=folder_id, uidvalidity=uidvalidity, uid=int(uid),
        subject=str(header.get("Subject", ""))[:500],
        sender=str(header.get("From", ""))[:500],
        recipients=str(header.get("To", ""))[:600],
        message_id=str(header.get("Message-ID", ""))[:240],
        sent_at=dt,
        size_bytes=int(size_match.group(1)) if size_match else 0,
        flags=flag_match.group(1)[:160] if flag_match else "",
    )


def sync_inbox(db, box, key, limit=30):
    """IMAP UID metadata sync. Safe to rerun; never downloads bodies or attachments."""
    limit = max(1, min(int(limit), 100))
    client = None
    count = 0
    try:
        client = _connect(box, key)
        typ, selected = client.select("INBOX", readonly=True)
        if typ != "OK":
            raise MailError("Nelze otevřít INBOX")
        if selected and selected[0] is not None:
            try:
                box.server_message_count = int(selected[0])
            except (ValueError, TypeError):
                box.server_message_count = None
        validity_raw = client.response("UIDVALIDITY")[1]
        uidvalidity = int(validity_raw[0]) if validity_raw and validity_raw[0] else 0
        if uidvalidity <= 0:
            raise MailError("Server neposkytl UIDVALIDITY; synchronizace je pozastavena")
        folder = db.scalar(select(MailFolder).where(MailFolder.mailbox_id == box.id, MailFolder.name == "INBOX"))
        if folder is None:
            folder = MailFolder(mailbox_id=box.id, name="INBOX", uidvalidity=uidvalidity)
            db.add(folder)
            db.flush()
        elif folder.uidvalidity != uidvalidity:
            folder.uidvalidity, folder.last_uid = uidvalidity, 0
        initial = folder.last_uid == 0
        if initial:
            typ, search = client.uid("SEARCH", None, "ALL")  # UID list only, no message data
        else:
            typ, search = client.uid("SEARCH", None, "UID", f"{folder.last_uid + 1}:*")
        if typ != "OK":
            raise MailError("Server odmítl UID SEARCH")
        found = sorted({int(x) for x in (search[0] or b"").split() if x.isdigit() and int(x) > folder.last_uid})
        ids = (found[-limit:] if initial else found[:limit])  # initial sync starts with newest messages
        for uid in ids:
            typ, item = client.uid("FETCH", str(uid), "(FLAGS RFC822.SIZE BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)])")
            if typ != "OK":
                raise MailError("Chyba při čtení hlaviček")
            message = parse_metadata(item, uid, box.id, folder.id, uidvalidity)
            old = db.scalar(select(MailMessage.id).where(MailMessage.folder_id == folder.id, MailMessage.uidvalidity == uidvalidity, MailMessage.uid == uid))
            if not old:
                db.add(message)
                count += 1
            folder.last_uid = uid
        box.status, box.sync_error, box.last_sync = "ok", "", now()
        db.commit()
        return count
    except Exception as ex:
        db.rollback()
        # Never persist raw IMAP exceptions, tokens or server traceback into customer-facing UI.
        description = str(ex)[:380] if isinstance(ex, MailError) else "IMAP synchronizace selhala. Zkontrolujte server a zkuste znovu."
        box.status, box.sync_error = "error", description
        db.commit()
        raise MailError(description) from None
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass


def preview_message(box, row, key, *, show_images=False, folder_name="INBOX"):
    """Fetch bounded MIME directly from IMAP; body and images stay out of MariaDB."""
    client = _connect(box, key)
    try:
        typ, _ = client.select(quote_mailbox_name(folder_name), readonly=True)
        if typ != "OK":
            raise MailError("Nelze otevřít složku zprávy")
        current = client.response("UIDVALIDITY")[1]
        if not current or int(current[0]) != row.uidvalidity:
            raise MailError("UID zprávy již neodpovídá serveru. Proveďte synchronizaci.")
        # A partial RFC822 fetch supplies MIME headers too, unlike BODY.PEEK[TEXT].
        # This caps decoded mail exposure and prevents large attachments being cached.
        typ, data = client.uid("FETCH", str(row.uid), f"(BODY.PEEK[]<0.{MAX_PREVIEW_BYTES}>)")
        if typ != "OK":
            raise MailError("Obsah zprávy není dostupný na IMAP serveru")
        buf = b"".join(item[1] for item in data if isinstance(item, tuple) and isinstance(item[1], bytes))
        if not buf:
            raise MailError("IMAP nevrátil obsah zprávy")
        return make_preview(buf[:MAX_PREVIEW_BYTES], show_images=show_images,
                            truncated=(row.size_bytes or 0) > MAX_PREVIEW_BYTES)
    finally:
        try:
            client.logout()
        except Exception:
            pass



def _parse_addresses(value, *, required=False):
    """Validate recipients; refuse header injection and large fanout."""
    if any(c in value for c in "\r\n") or len(value) > 1500:
        raise MailError("Neplatný seznam příjemců")
    result = []
    for _, addr in getaddresses([value.replace(";", ",")]):
        if not addr or not re.fullmatch(r"[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+", addr) or len(addr) > 254:
            raise MailError("Zkontrolujte formát adres příjemců")
        result.append(addr)
    if (required and not result) or len(result) > 25:
        raise MailError("Vyberte 1–25 příjemců")
    return list(dict.fromkeys(result))


def send_composed(box, key, to, cc, bcc, subject, body, *, reply_message_id=None, attachments=None):
    """Only explicit SMTP send. No retry if delivery outcome is uncertain."""
    primary = _parse_addresses(to, required=True)
    copy = _parse_addresses(cc)
    blind = _parse_addresses(bcc)
    if len(primary) + len(copy) + len(blind) > 25:
        raise MailError("Příliš mnoho příjemců")
    if not subject or len(subject) > 500 or any(c in subject for c in "\r\n"):
        raise MailError("Neplatný předmět")
    if not body.strip() or len(body) > 100000:
        raise MailError("Text zprávy chybí nebo překračuje limit")
    if any(c in box.address for c in "\r\n"):
        raise MailError("Neplatná adresa odesílatele")
    validate_mail_host(box.smtp_host)
    if box.smtp_port not in (465, 587):
        raise MailError("SMTP vyžaduje TLS na portu 465 nebo 587")
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = box.address, ", ".join(primary), subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    if copy:
        msg["Cc"] = ", ".join(copy)
    if reply_message_id:
        if len(reply_message_id) > 250 or any(c in reply_message_id for c in "\r\n") or not (
            reply_message_id.startswith("<") and reply_message_id.endswith(">")
        ):
            raise MailError("Neplatná reference původního e-mailu")
        msg["In-Reply-To"] = reply_message_id
        msg["References"] = reply_message_id
    msg.set_content(body)
    total_size = 0
    for name, data in attachments or []:
        total_size += len(data)
        if total_size > 10_000_000 or len(data) > 6_000_000:
            raise MailError("Přílohy přesahují limit 10 MB / 6 MB na soubor")
        filename = PurePath(name.replace("\\", "/")).name
        if not filename or len(filename) > 140 or any(c in filename for c in "\r\n\x00"):
            raise MailError("Neplatný název přílohy")
        msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=filename)
    password = decrypt_password(box.credential, key)
    recipients = list(dict.fromkeys(primary + copy + blind))
    try:
        if box.smtp_port == 465:
            with smtplib.SMTP_SSL(box.smtp_host, 465, timeout=20, context=ssl.create_default_context()) as smtp:
                smtp.login(getattr(box, "smtp_username", "") or box.username, password)
                smtp.send_message(msg, to_addrs=recipients)
        else:
            with smtplib.SMTP(box.smtp_host, 587, timeout=20) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(getattr(box, "smtp_username", "") or box.username, password)
                smtp.send_message(msg, to_addrs=recipients)
    except smtplib.SMTPAuthenticationError as ex:
        raise MailError("SMTP odmítlo přihlášení. Ověř SMTP login, heslo a nastavení portu 465/587.") from ex
    except smtplib.SMTPRecipientsRefused as ex:
        raise MailError("SMTP odmítlo alespoň jednoho příjemce. Zkontroluj adresy.") from ex
    except (ssl.SSLError, socket.timeout, TimeoutError, OSError) as ex:
        raise MailError("SMTP spojení selhalo nebo vypršelo; výsledek odeslání může být nejistý.") from ex
    except Exception as ex:
        raise MailError("SMTP odeslání není potvrzené; ověř doručení před opakováním") from ex
    return msg.as_bytes()


def send_plain(box, key, to_addr, subject, text):
    """One explicit, user-approved SMTP send. No automatic retry on uncertain outcome."""
    if "@" not in to_addr or any(x in to_addr for x in "\r\n"):
        raise MailError("Neplatná adresa příjemce")
    if any(c in subject for c in "\r\n") or any(c in box.address for c in "\r\n"):
        raise MailError("Neplatná hlavička zprávy")
    if len(subject) > 500 or len(text) > 100000:
        raise MailError("Zpráva překračuje limit")
    validate_mail_host(box.smtp_host)
    if box.smtp_port not in (465, 587):
        raise MailError("SMTP vyžaduje TLS na portu 465 nebo 587")
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = box.address, to_addr, subject
    msg.set_content(text)
    password = decrypt_password(box.credential, key)
    try:
        if box.smtp_port == 465:
            with smtplib.SMTP_SSL(box.smtp_host, 465, timeout=20, context=ssl.create_default_context()) as smtp:
                smtp.login(getattr(box, "smtp_username", "") or box.username, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(box.smtp_host, 587, timeout=20) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(getattr(box, "smtp_username", "") or box.username, password)
                smtp.send_message(msg)
    except Exception as ex:
        raise MailError("SMTP odeslání není potvrzené; ověřte schránku před opakováním") from ex