"""Actual external contact CSV shapes must be usable without editing headers."""
import pytest

from ema.contact_import import ImportErrorCSV, extract_contacts, normalize_header


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


def test_broken_email_remains_invalid():
    with pytest.raises(ImportErrorCSV, match="neplatn"):
        extract_contacts(b"Email Address\nnot-a-valid-address\n")


def test_header_normalization_is_stable():
    assert normalize_header("E-mail 1 - Value") == "e mail 1 value"
    assert normalize_header("Organization 1 - Name") == "organization 1 name"
    assert normalize_header("E-mail Address") == "e mail address"
