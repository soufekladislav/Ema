"""Actual external contact CSV shapes must be usable without editing headers."""
import pytest

from ema.contact_import import ImportErrorCSV, analyze_contacts, extract_contacts, normalize_header
from tests.test_navigation import web_client, login, csrf


def test_google_contacts_csv_without_name_and_phone():
    csv_data = (
        "Name,Given Name,Family Name,E-mail 1 - Type,E-mail 1 - Value,"
        "Phone 1 - Value,Organization 1 - Name\n"
        ",,,,prospect@example.cz,,Acme\n"
    ).encode("utf-8")
    contacts = extract_contacts(csv_data)
    assert len(contacts) == 1
    assert contacts[0]["name"] == "prospect@example.cz"
    assert contacts[0]["email"] == "prospect@example.cz"
    assert contacts[0]["phone"] == ""
    assert contacts[0]["company_name"] == "Acme"


def test_outlook_csv_and_alternative_phone_fields():
    csv_data = (
        "First Name;Last Name;E-mail Address;Mobile Phone;Company\n"
        "Josef;Novak;jozef@example.cz;+420777333444;Consulting\n"
    ).encode("utf-8")
    contact = extract_contacts(csv_data)[0]
    assert contact["name"] == "Josef Novak"
    assert contact["phone"] == "+420777333444"
    assert contact["company_name"] == "Consulting"


def test_phone_only_csv_is_allowed_and_identifiable():
    contact = extract_contacts(
        b"Phone 1 - Value\n+420777222333\n"
    )[0]
    assert contact["phone"] == "+420777222333"
    assert contact["email"] == ""
    assert contact["name"] == "+420777222333"


def test_unknown_headers_are_reported_instead_of_guessing():
    with pytest.raises(ImportErrorCSV, match="hlav"):
        extract_contacts(b"Personal ID;Extra\nx;y\n")


def test_broken_email_is_review_only_not_a_deliverable_address():
    contacts, report = analyze_contacts(b"Email Address\nnot-a-valid-address\n")
    assert len(contacts) == 1
    assert contacts[0]["email"] == ""
    assert contacts[0]["attributes"]["email_k_overeni"] == "not-a-valid-address"
    assert contacts[0]["attributes"]["email_stav"] == "neovereny"
    assert report["invalid_email_rows"] == 1
    assert report["needs_review"] == 1


def test_header_normalization_is_stable():
    assert normalize_header("E-mail 1 - Value") == "e mail 1 value"
    assert normalize_header("Organization 1 - Name") == "organization 1 name"
    assert normalize_header("E-mail Address") == "e mail address"



def test_phone_only_google_csv_import_replays_as_same_contact(web_client):
    import io
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from ema.models import Contact, ContactOrigin

    client = web_client
    login(client, "owner")
    org = client.application.ids["org"]
    data = b"Phone 1 - Value\n+420777123321\n"
    for _ in range(2):
        result = client.post("/database/import", data={
            "organization_id": str(org), "source_name": "Google Phone",
            "mode": "import", "csrf_token": csrf(client),
            "file": (io.BytesIO(data), "google_phone.csv")
        }, content_type="multipart/form-data")
        assert result.status_code == 302
    with Session(client.application.extensions["ema_engine"]) as db:
        rows = db.scalars(select(Contact).where(Contact.phone == "+420777123321")).all()
        assert len(rows) == 1
        assert rows[0].email == ""
        assert rows[0].organization_id == org
        assert len(db.scalars(select(ContactOrigin).where(ContactOrigin.contact_id == rows[0].id)).all()) == 1



def test_google_row_81_invalid_does_not_cancel_100_other_contacts():
    lines = ["Name,E-mail 1 - Value,Phone 1 - Value"]
    for row in range(2, 103):
        email = "not-an-email" if row == 81 else f"user{row}@example.test"
        lines.append(f"Osoba{row},{email},")
    contacts, report = analyze_contacts(("\n".join(lines) + "\n").encode("utf-8"))
    assert len(contacts) == 101
    assert report["read_rows"] == 101
    assert report["invalid_email_rows"] == 1
    assert report["needs_review"] == 1
    assert report["problem_rows"] == [81]
    problem = [r for r in contacts if r["name"] == "Osoba81"]
    assert len(problem) == 1
    assert problem[0]["email"] == ""
    assert problem[0]["attributes"]["email_k_overeni"] == "not-an-email"
    assert contacts[-1]["email"] == "user102@example.test"


def test_invalid_first_email_uses_valid_secondary_and_preserves_warning():
    contacts, report = analyze_contacts(
        b"Name,E-mail 1 - Value,E-mail 2 - Value\nEva,bad-address,eva@example.cz\n"
    )
    assert contacts[0]["email"] == "eva@example.cz"
    assert contacts[0]["attributes"]["email_k_overeni"] == "bad-address"
    assert report["invalid_email_rows"] == 1
    assert report["needs_review"] == 0


def test_email_field_with_two_addresses_is_not_deliverable():
    contacts, report = analyze_contacts(
        b"Name;Email Address\nUser;person@example.cz;other@example.cz\n".replace(
            b"person@example.cz;other@example.cz", b"person@example.cz,other@example.cz"
        )
    )
    assert contacts[0]["email"] == ""
    assert report["invalid_email_rows"] == 1


def test_google_csv_invalid_email_import_and_replay_preserve_source(web_client):
    import io
    import json
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from ema.models import Contact, ContactOrigin

    client = web_client
    login(client, "owner")
    org = client.application.ids["org"]
    lines = ["Name,E-mail 1 - Value"]
    for row in range(2, 85):
        email = "bad-email" if row == 81 else f"google{row}@example.test"
        lines.append(f"Google Person {row},{email}")
    csv_payload = ("\n".join(lines) + "\n").encode("utf-8")

    # Preview is read only and reports which row needs correction.
    res = client.post("/database/import", data={
        "organization_id": str(org), "source_name": "Google Contacts",
        "mode": "preview", "csrf_token": csrf(client),
        "file": (io.BytesIO(csv_payload), "google.csv"),
    }, content_type="multipart/form-data", follow_redirects=True)
    assert res.status_code == 200
    assert "81" in res.get_data(as_text=True)
    assert "neplatnou adresou" in res.get_data(as_text=True)
    with Session(client.application.extensions["ema_engine"]) as db:
        assert db.scalar(select(Contact.id).where(Contact.name == "Google Person 81")) is None

    # Two imports use the existing provenance logic and must not duplicate rows.
    for repeat in range(2):
        res = client.post("/database/import", data={
            "organization_id": str(org), "source_name": "Google Contacts",
            "mode": "import", "csrf_token": csrf(client),
            "file": (io.BytesIO(csv_payload), "google.csv"),
        }, content_type="multipart/form-data", follow_redirects=True)
        assert res.status_code == 200
        assert "neplatnou adresou" in res.get_data(as_text=True)
    with Session(client.application.extensions["ema_engine"]) as db:
        contacts = db.scalars(select(Contact).where(
            Contact.organization_id == org,
            Contact.name.like("Google Person %"))).all()
        assert len(contacts) == 83
        problem = next(c for c in contacts if c.name == "Google Person 81")
        assert problem.email == ""
        metadata = json.loads(problem.metadata_json)
        assert metadata["fields"]["email_stav"] == "neovereny"
        assert metadata["fields"]["email_k_overeni"] == "bad-email"
        sources = db.scalars(select(ContactOrigin).where(
            ContactOrigin.contact_id == problem.id)).all()
        assert len(sources) == 1
        assert sources[0].source_site == "CSV: Google Contacts"
    response = client.get("/database?q=Google%20Person%2081")
    assert response.status_code == 200
    assert "E-mail k ověření" in response.get_data(as_text=True)
