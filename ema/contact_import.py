"""Bounded CSV parser for authorized per-company contact imports. Never writes directly."""
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
    # Normalize Google Contacts "E-mail 1 - Value" and Outlook "E-mail Address".
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", normalized)).strip()


def extract_contacts(data):
    """Return up to 1000 contacts with metadata, without exposing original CSV outside caller."""
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
    headers = [(normalize_header(h), h) for h in reader.fieldnames]
    if len({h[0] for h in headers}) != len(headers):
        raise ImportErrorCSV("CSV obsahuje duplicitní názvy sloupců.")
    collected = []
    for index, record in enumerate(reader, 2):
        if index > 1002:
            raise ImportErrorCSV("V jedné dávce lze importovat maximálně 1000 kontaktů.")
        if None in record:
            raise ImportErrorCSV(f"Řádek {index} má jiný počet sloupců než hlavička.")
        fields = {normalize_header(key): str(value or "").strip() for key, value in record.items()}
        if not any(fields.values()):
            continue
        def pick(*names):
            return next((fields.get(k, "") for k in names if fields.get(k, "")), "")
        # Recognize native CSV field headers from Google Contacts and Outlook.
        # Never infer personal identities from unrelated free-text columns.
        name_keys = ("name", "full name", "cele jmeno", "kontakt", "contact", "display name")
        first_keys = ("jmeno", "first name", "firstname", "given name")
        last_keys = ("prijmeni", "last name", "lastname", "family name", "surname")
        email_keys = ("email", "e mail", "mail", "e mailova adresa", "email address",
                      "email 1 value", "email 2 value", "email 3 value",
                      "emailaddress", "primary email", "email address 1", "email address 2")
        phone_keys = ("telefon", "phone", "mobile", "mobil", "tel", "mobile phone",
                      "business phone", "home phone", "primary phone",
                      "phone 1 value", "phone 2 value", "phone 3 value",
                      "telephone", "phone number", "telefonni cislo")
        company_keys = ("firma", "company", "organization", "spolecnost",
                        "organization 1 name", "company name", "business name")
        first = pick(*first_keys)
        last = pick(*last_keys)
        name = pick(*name_keys) or (first + " " + last).strip()
        email = pick(*email_keys).lower()
        phone = pick(*phone_keys)
        company = pick(*company_keys)
        if email and not re.fullmatch(r"[^\\s@]+@[^\\s@]+\\.[^\\s@]+", email):
            raise ImportErrorCSV(f"Řádek {index}: neplatný formát e-mailu.")
        if not (name or email or phone):
            raise ImportErrorCSV(
                f"Řádek {index}: nelze rozpoznat jméno, e-mail ani telefon. "
                "Zkontrolujte hlavičky CSV (např. Email Address, E-mail 1 - Value, Phone 1 - Value)."
            )
        if not name:
            name = email or phone
        used = set(name_keys + first_keys + last_keys + email_keys + phone_keys + company_keys)
        custom = {key: value[:300] for key, value in fields.items() if key not in used and value}
        if len(json.dumps(custom, ensure_ascii=False)) > 4000:
            raise ImportErrorCSV(f"Řádek {index}: příliš rozsáhlá metadata.")
        collected.append({"name": name[:190], "email": email[:190], "phone": phone[:60],
                          "company_name": company[:190], "attributes": custom})
    if not collected:
        raise ImportErrorCSV("CSV neobsahuje žádné platné kontakty.")
    return collected
