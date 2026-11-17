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
    return "".join(c for c in plain if not unicodedata.combining(c)).replace("_", " ").strip()


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
        first = pick("jmeno", "first name", "firstname")
        last = pick("prijmeni", "last name", "lastname")
        name = pick("name", "full name", "cele jmeno", "kontakt", "contact") or (first + " " + last).strip()
        email = pick("email", "e mail", "e-mail", "mail", "e-mailova adresa").lower()
        phone = pick("telefon", "phone", "mobile", "mobil", "tel")
        company = pick("firma", "company", "organization", "spolecnost")
        if not name:
            name = email
        if not name:
            raise ImportErrorCSV(f"Řádek {index}: chybí jméno i e-mail.")
        if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise ImportErrorCSV(f"Řádek {index}: neplatný formát e-mailu.")
        used = {"name", "full name", "cele jmeno", "kontakt", "contact",
                "jmeno", "first name", "firstname", "prijmeni", "last name", "lastname",
                "email", "e mail", "e-mail", "mail", "e-mailova adresa", "telefon", "phone",
                "mobile", "mobil", "tel", "firma", "company", "organization", "spolecnost"}
        custom = {key: value[:300] for key, value in fields.items() if key not in used and value}
        if len(json.dumps(custom, ensure_ascii=False)) > 4000:
            raise ImportErrorCSV(f"Řádek {index}: příliš rozsáhlá metadata.")
        collected.append({"name": name[:190], "email": email[:190], "phone": phone[:60],
                          "company_name": company[:190], "attributes": custom})
    if not collected:
        raise ImportErrorCSV("CSV neobsahuje žádné platné kontakty.")
    return collected
