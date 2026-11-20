"""Regression coverage for CRM batch import and repeatable additive migrations."""
import io

import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from ema.contact_import import ImportErrorCSV, MAX_CSV_BYTES, MAX_CSV_ROWS, analyze_contacts
from ema.models import Contact, ContactOrigin
from ema.schema_upgrade import upgrade_schema
from tests.test_navigation import web_client, login, csrf


def bulk_csv(count=2500):
    lines = ["Name,E-mail 1 - Value,Notes"]
    # Deliberately >1 MB to cover both the old 950 kB CSV parser limit
    # and the former 1 MB Flask request cap.
    note = "x" * 430
    for i in range(count):
        lines.append(f"Contact {i:04d},bulk{i:04d}@example.test,{note}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def test_csv_2500_rows_and_over_one_megabyte_are_accepted():
    payload = bulk_csv()
    assert 1024 * 1024 < len(payload) < MAX_CSV_BYTES
    entries, report = analyze_contacts(payload)
    assert len(entries) == 2500
    assert report["contact_rows"] == 2500
    assert report["invalid_email_rows"] == 0


def test_bounded_import_rejects_excessive_rows_and_bytes():
    with pytest.raises(ImportErrorCSV, match="5000"):
        analyze_contacts(b"Name,Email\n" +
                         b"Person,person@example.test\n" * (MAX_CSV_ROWS + 1))
    with pytest.raises(ImportErrorCSV, match="5 MB"):
        analyze_contacts(b"Name,Email\n" + b"x" * MAX_CSV_BYTES)


def test_http_import_2500_and_replay_are_atomic_and_idempotent(web_client):
    client = web_client
    login(client, "owner")
    org = client.application.ids["org"]
    payload = bulk_csv()
    engine = client.application.extensions["ema_engine"]

    def post(mode):
        return client.post("/database/import", data={
            "organization_id": str(org), "source_name": "Kontakty 2500",
            "mode": mode, "csrf_token": csrf(client),
            "file": (io.BytesIO(payload), "contacts.csv"),
        }, content_type="multipart/form-data")

    preview = post("preview")
    assert preview.status_code == 302
    with Session(engine) as db:
        assert db.scalar(select(func.count(Contact.id)).where(
            Contact.organization_id == org)) == 0

    first = post("import")
    assert first.status_code == 302
    with Session(engine) as db:
        assert db.scalar(select(func.count(Contact.id)).where(
            Contact.organization_id == org)) == 2500
        assert db.scalar(select(func.count(ContactOrigin.id)).where(
            ContactOrigin.organization_id == org, ContactOrigin.source_kind == "csv")) == 2500

    replay = post("import")
    assert replay.status_code == 302
    with Session(engine) as db:
        assert db.scalar(select(func.count(Contact.id)).where(
            Contact.organization_id == org)) == 2500
        assert db.scalar(select(func.count(ContactOrigin.id)).where(
            ContactOrigin.organization_id == org, ContactOrigin.source_kind == "csv")) == 2500


def test_upgrade_restores_company_origins_without_losing_contacts(web_client):
    engine = web_client.application.extensions["ema_engine"]
    org = web_client.application.ids["org"]
    with Session(engine) as db:
        db.add(Contact(organization_id=org, name="Zachovaný kontakt",
                       email="saved@example.test"))
        db.commit()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE company_origins"))
    assert not inspect(engine).has_table("company_origins")

    applied = upgrade_schema(engine)
    assert "table company_origins" in applied
    assert inspect(engine).has_table("company_origins")
    assert "table company_origins" not in upgrade_schema(engine)
    with Session(engine) as db:
        assert db.scalar(select(func.count(Contact.id)).where(
            Contact.organization_id == org, Contact.email == "saved@example.test")) == 1
