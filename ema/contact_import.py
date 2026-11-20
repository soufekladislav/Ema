"""Bounded CSV parser for authorized per-company contact imports.

A malformed email is not a reason to throw away the entire contact database.
It is retained for later review, never as a deliverable email address.
"""
import csv
import io
import json
import re
import unicodedata


class ImportErrorCSV(Exception):
    pass


def normalize_header(value):
    plain = unicodedata.normalize("NFKD", (value or "").strip().lower())
    normalized = "".join(c for c in plain if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", normalized)).strip()


NAME_KEYS = ("name", "full name", "cele jmeno", "kontakt", "contact", "display name")
FIRST_KEYS = ("jmeno", "first name", "firstname", "given name")
LAST_KEYS = ("prijmeni", "last name", "lastname", "family name", "surname")
EMAIL_KEYS = ("email", "e mail", "mail", "e mailova adresa",
              "email address", "e mail address", "emailaddress",
              "email 1 value", "email 2 value", "email 3 value",
              "e mail 1 value", "e mail 2 value", "e mail 3 value",
              "primary email", "email address 1", "email address 2")
PHONE_KEYS = ("telefon", "phone", "mobile", "mobil", "tel", "mobile phone",
              "business phone", "home phone", "primary phone",
              "phone 1 value", "phone 2 value", "phone 3 value",
              "telephone", "phone number", "telefonni cislo")
COMPANY_KEYS = ("firma", "company", "organization", "spolecnost",
                "organization 1 name", "company name", "business name")
KNOWN_KEYS = set(NAME_KEYS + FIRST_KEYS + LAST_KEYS + EMAIL_KEYS + PHONE_KEYS + COMPANY_KEYS)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def analyze_contacts(data):
    """Return (valid CRM entries, bounded summary); never expose CSV row values in errors.

    Invalid email strings remain in each entry's review-only metadata; the
    canonical email stays empty until a person verifies it. A Google contact
    with a second valid address keeps that valid address instead.
    """
    if not data or len(data) > 950_000:
        raise ImportErrorCSV("CSV je prázdné nebo přesahuje limit 950 kB.")
    try:
        decoded = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = data.decode("cp1250", errors="replace")
    sample = decoded[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(decoded, newline=""), dialect=dialect)
    if not reader.fieldnames or len(reader.fieldnames) > 60:
        raise ImportErrorCSV("CSV musí mít hlavičku a maximálně 60 sloupců.")
    headers = [normalize_header(h) for h in reader.fieldnames]
    if len(set(headers)) != len(headers):
        raise ImportErrorCSV("CSV obsahuje duplicitní názvy sloupců.")
    if not (set(headers) & KNOWN_KEYS):
        raise ImportErrorCSV(
            "CSV má nerozpoznané hlavičky. Použijte např. Jméno, E-mail, "
            "Email Address, E-mail 1 - Value nebo Phone 1 - Value."
        )

    collected = []
    report = {"read_rows": 0, "invalid_email_rows": 0,
              "needs_review": 0, "skipped_rows": 0, "problem_rows": []}
    for index, record in enumerate(reader, 2):
        if index > 1002:
            raise ImportErrorCSV("V jedné dávce lze importovat maximálně 1000 kontaktů.")
        if None in record:
            raise ImportErrorCSV(f"Řádek {index} má jiný počet sloupců než hlavička.")
        fields = {normalize_header(k): str(v or "").strip() for k, v in record.items()}
        if not any(fields.values()):
            continue
        report["read_rows"] += 1

        def pick(*names):
            return next((fields.get(k, "") for k in names if fields.get(k, "")), "")

        name = pick(*NAME_KEYS) or (pick(*FIRST_KEYS) + " " + pick(*LAST_KEYS)).strip()
        phone = pick(*PHONE_KEYS)
        company = pick(*COMPANY_KEYS)
        candidate_emails = [fields[k].strip() for k in EMAIL_KEYS if fields.get(k)]
        valid = [value.lower() for value in candidate_emails
                 if len(value) <= 190 and EMAIL_RE.fullmatch(value)]
        invalid = [value for value in candidate_emails
                   if len(value) > 190 or not EMAIL_RE.fullmatch(value)]
        email = valid[0] if valid else ""
        attrs = {key: value[:300] for key, value in fields.items()
                 if key not in KNOWN_KEYS and value}
        if invalid:
            report["invalid_email_rows"] += 1
            if len(report["problem_rows"]) < 12:
                report["problem_rows"].append(index)
            # Review-only copy, not Contact.email: cannot be used to send mail.
            attrs["email_k_overeni"] = invalid[0][:190]
            if not email:
                report["needs_review"] += 1
                attrs["email_stav"] = "neovereny"
        if not (name or email or phone) and not invalid:
            report["skipped_rows"] += 1
            if len(report["problem_rows"]) < 12:
                report["problem_rows"].append(index)
            continue
        # An invalid-only Google address is kept as a reviewable contact,
        # not silently lost; there is no deliverable email.
        if not name:
            name = email or phone or ("Kontakt k ověření: " + invalid[0][:140])
        if len(json.dumps(attrs, ensure_ascii=False)) > 4000:
            report["skipped_rows"] += 1
            if len(report["problem_rows"]) < 12:
                report["problem_rows"].append(index)
            continue
        collected.append({
            "name": name[:190], "email": email[:190], "phone": phone[:60],
            "company_name": company[:190], "attributes": attrs
        })

    if not collected:
        raise ImportErrorCSV(
            "CSV neobsahuje použitelné kontakty. Zkontrolujte hlavičky, "
            "jména, telefony a neplatné e-maily."
        )
    return collected, report


def extract_contacts(data):
    """Backwards-compatible function used by existing Ema code and tests."""
    return analyze_contacts(data)[0]
