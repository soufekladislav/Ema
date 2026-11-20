"""Real CSV form: 100 acquisition companies without personal contact fields."""
import csv
import io
import json

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ema.contact_import import analyze_contacts
from ema.models import Company, CompanyOrigin, Contact
from tests.test_navigation import web_client, login, csrf


HEADERS = [
    "Firma", "Kraj", "Město", "Obor", "Obrat", "Rok obratu", "Růst tržeb", "Web",
    "Hypotéza nabídky (neověřeno)", "Priorita", "Zdroj", "Stav ověření",
    "E-commerce / online objednávky",
    "Pozorování z webu (ověřeno vs hypotéza)", "Možná slabina – k prověření",
    "Doporučená služba Fresh Crackers", "Úhel prvního oslovení",
    "Stav e-commerce ověření", "Facebook profil – ověřený odkaz",
    "LinkedIn profil – ověřený odkaz", "Obchodní připravenost",
]


def firm_csv(count=100):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=HEADERS)
    writer.writeheader()
    for i in range(1, count+1):
        writer.writerow({
            "Firma": f"Firma Kandidát {i:03d} s.r.o.",
            "Kraj": "Středočeský",
            "Město": "Praha",
            "Obor": "výrobce",
            "Obrat": "neověřeno",
            "Rok obratu": "2024",
            "Růst tržeb": "neověřeno",
            "Web": f"https://example{i:03d}.test/",
            "Hypotéza nabídky (neověřeno)": "pravděpodobně potřebuje nový web",
            "Priorita": "A",
            "Zdroj": "vlastní akviziční rešerše",
            "Stav ověření": "nutno ověřit",
            "E-commerce / online objednávky": "neověřeno",
            "Pozorování z webu (ověřeno vs hypotéza)": "hypotéza",
            "Možná slabina – k prověření": "SEO",
            "Doporučená služba Fresh Crackers": "AI audit",
            "Úhel prvního oslovení": "kontakt až po ověření",
            "Stav e-commerce ověření": "neověřeno",
            "Facebook profil – ověřený odkaz": "neověřeno",
            "LinkedIn profil – ověřený odkaz": "neověřeno",
            "Obchodní připravenost": "hypotéza",
        })
    return output.getvalue().encode("utf-8-sig")


def post_csv(client, org, payload, mode="preview", source="Akvizice 100 firem"):
    return client.post("/database/import", data={
        "organization_id": str(org), "source_name": source,
        "mode": mode, "csrf_token": csrf(client),
        "file": (io.BytesIO(payload), "kandidati.csv"),
    }, content_type="multipart/form-data", follow_redirects=True)


def test_exact_21_company_csv_columns_are_accepted_without_persons():
    entries, report = analyze_contacts(firm_csv())
    assert len(entries) == 100
    assert report["company_rows"] == 100
    assert report["contact_rows"] == 0
    assert report["skipped_rows"] == 0
    assert all(r["entity_type"] == "company" for r in entries)
    assert all(not r["name"] and not r["email"] and not r["phone"] for r in entries)
    attrs = entries[0]["attributes"]
    assert attrs["Web"] == "https://example001.test/"
    assert attrs["Hypotéza nabídky (neověřeno)"] == "pravděpodobně potřebuje nový web"
    assert attrs["Priorita"] == "A"
    assert attrs["Zdroj"] == "vlastní akviziční rešerše"
    assert attrs["Obchodní připravenost"] == "hypotéza"


def test_firm_only_csv_preview_then_import_and_replay(web_client):
    client = web_client
    login(client, "owner")
    org = client.application.ids["org"]
    engine = client.application.extensions["ema_engine"]
    payload = firm_csv()
    first = post_csv(client, org, payload)
    html = first.get_data(as_text=True)
    assert first.status_code == 200
    assert "100 firem bez kontaktní osoby" in html
    with Session(engine) as db:
        assert db.scalar(select(func.count(Company.id)).where(
            Company.organization_id == org)) == 0

    for _ in range(2):
        response = post_csv(client, org, payload, "import")
        assert response.status_code == 200

    with Session(engine) as db:
        companies = db.scalars(select(Company).where(
            Company.organization_id == org).order_by(Company.name)).all()
        assert len(companies) == 100
        origins = db.scalars(select(CompanyOrigin).where(
            CompanyOrigin.organization_id == org)).all()
        assert len(origins) == 100
        assert all(x.source_site == "CSV: Akvizice 100 firem" for x in origins)
        assert db.scalar(select(func.count(Contact.id)).where(
            Contact.organization_id == org,
            Contact.name.like("Firma Kandidát %"))) == 0
        first_company = companies[0]
        first_origin = next(o for o in origins if o.company_id == first_company.id)
        fields = json.loads(first_origin.metadata_json)["fields"]
        assert fields["Web"] == "https://example001.test/"
        assert fields["Zdroj"] == "vlastní akviziční rešerše"
        assert fields["Stav ověření"] == "nutno ověřit"
        assert json.loads(first_origin.metadata_json)["review_status"] == "unverified"

    page = client.get("/database")
    assert page.status_code == 200
    assert "Klientské firmy" in page.get_data(as_text=True)
    details = client.get(f"/org/{org}/clients")
    assert details.status_code == 200
    body = details.get_data(as_text=True)
    assert "Firma Kandidát 001 s.r.o." in body
    assert "https://example001.test/" in body
    assert "vlastní akviziční rešerše" in body


def test_same_firm_from_different_sources_retains_both_origins_and_edits(web_client):
    client = web_client
    login(client, "owner")
    org = client.application.ids["org"]
    engine = client.application.extensions["ema_engine"]
    payload = firm_csv(1)
    assert post_csv(client, org, payload, "import", "První seznam").status_code == 200
    with Session(engine) as db:
        company = db.scalar(select(Company).where(Company.organization_id == org))
        assert company
        cid = company.id
    edit = client.post(f"/org/{org}/clients/{cid}/edit", data={
        "csrf_token": csrf(client), "name": "Firma Kandidát 001 s.r.o.",
        "ico": "12345678", "email": "info@example.test", "phone": "+420123456789",
        "notes": "Ověřit majitele a telefon.",
    }, follow_redirects=True)
    assert edit.status_code == 200
    assert post_csv(client, org, payload, "import", "Druhý seznam").status_code == 200
    with Session(engine) as db:
        rows = db.scalars(select(Company).where(
            Company.organization_id == org)).all()
        assert len(rows) == 1
        company = rows[0]
        assert company.ico == "12345678"
        assert company.email == "info@example.test"
        assert company.notes == "Ověřit majitele a telefon."
        sources = db.scalars(select(CompanyOrigin).where(
            CompanyOrigin.organization_id == org)).all()
        assert len(sources) == 2
        assert set(s.source_site for s in sources) == {
            "CSV: První seznam", "CSV: Druhý seznam"}


def test_company_imports_are_isolated_by_owner_company(web_client):
    client = web_client
    login(client, "owner")
    engine = client.application.extensions["ema_engine"]
    org_a = client.application.ids["org"]
    org_b = client.application.ids["secret_org"]
    payload = firm_csv(1)
    assert post_csv(client, org_a, payload, "import").status_code == 200
    assert post_csv(client, org_b, payload, "import").status_code == 200
    with Session(engine) as db:
        assert db.scalar(select(func.count(Company.id))) == 2
        assert db.scalar(select(func.count(CompanyOrigin.id))) == 2
    login(client, "guest")
    assert client.get(f"/org/{org_a}/clients").status_code in (302, 403)
    result = client.post(f"/org/{org_a}/clients/1/edit", data={
        "csrf_token": csrf(client), "name": "Nesmí změnit"})
    assert result.status_code in (302, 403, 404)


def test_mixed_contacts_and_companies_no_fake_people(web_client):
    client = web_client
    login(client, "owner")
    org = client.application.ids["org"]
    data = (
        "Firma;Jméno;E-mail;Telefon;Web\n"
        "Alpha s.r.o.;;;;https://alpha.test\n"
        "Beta s.r.o.;Jan Test;jan@example.test;;https://beta.test\n"
    ).encode()
    response = post_csv(client, org, data, "import", "Mixed")
    assert response.status_code == 200
    engine = client.application.extensions["ema_engine"]
    with Session(engine) as db:
        assert db.scalar(select(func.count(Company.id)).where(
            Company.organization_id == org)) == 1
        contact = db.scalar(select(Contact).where(
            Contact.organization_id == org))
        assert contact.name == "Jan Test"
        assert contact.email == "jan@example.test"
