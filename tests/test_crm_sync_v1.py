"""CRM acceptance: existing contacts, provenance, CSV, scoped Fresh Core sync."""
import io
import json
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from ema.models import Contact, ContactOrigin, FreshCoreSource, Organization
from ema.fresh_core_contacts import FreshCoreError, ingest_contacts
from tests.test_navigation import web_client, login, csrf


def _contact(source_id, email="klient@example.cz", **kwargs):
    return dict(source_id=source_id, email=email, name="Klient Test",
                company="Klient s.r.o.", phone="777123456", **kwargs)


def test_import_from_wordpress_elementor_and_csv_shares_one_crm(web_client, monkeypatch):
    client = web_client
    login(client, "owner")
    org = client.application.ids["org"]
    client.application.config["MAIL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    import ema.web as web
    monkeypatch.setattr(web, "canonical_site", lambda raw: "https://www.freshcrackers.cz")
    def fake_page(source, key, kind, *, after=0, limit=50):
        assert source.site_url == "https://www.freshcrackers.cz"
        assert key == client.application.config["MAIL_ENCRYPTION_KEY"]
        rows = [_contact(101)] if kind == "users" else [_contact(212)]
        return {"ok": True, "available": True, "site": source.site_url,
                "kind": kind, "items": rows, "next_after_id": rows[0]["source_id"],
                "has_more": False}
    monkeypatch.setattr(web, "fetch_page", fake_page)
    import ema.fresh_core_contacts as service
    monkeypatch.setattr(service, "fetch_page", fake_page)
    post = client.post("/database/sources", data={
        "csrf_token": csrf(client), "organization_id": str(org),
        "site_url": "https://www.freshcrackers.cz",
        "accounting_read_key": "a" * 64})
    assert post.status_code == 302
    with Session(client.application.extensions["ema_engine"]) as db:
        sources = db.scalars(select(FreshCoreSource)).all()
        assert len(sources) == 1
        assert sources[0].credential != "a" * 64
        sid = sources[0].id
    assert client.post(f"/database/sources/{sid}/preview",
                       data={"csrf_token": csrf(client)}).status_code == 302
    with Session(client.application.extensions["ema_engine"]) as db:
        assert not db.scalars(select(Contact).where(Contact.email == "klient@example.cz")).all()
    for _ in range(2):
        r = client.post(f"/database/sources/{sid}/sync",
                        data={"csrf_token": csrf(client)})
        assert r.status_code == 302
    with Session(client.application.extensions["ema_engine"]) as db:
        contacts = db.scalars(select(Contact).where(Contact.email == "klient@example.cz")).all()
        assert len(contacts) == 1
        assert contacts[0].organization_id == org
        assert len(db.scalars(select(ContactOrigin).where(
            ContactOrigin.contact_id == contacts[0].id)).all()) == 2
    assert "klient@example.cz" in client.get("/database?q=klient").get_data(as_text=True)
    assert "klient@example.cz" in client.get("/database?kind=users").get_data(as_text=True)
    assert "klient@example.cz" in client.get("/database?kind=elementor_submissions").get_data(as_text=True)
    assert "klient@example.cz" not in client.get("/database?kind=csv").get_data(as_text=True)
    rows = "Jméno;E-mail;Firma;Zdroj\nKlient Test;klient@example.cz;Klient s.r.o.;akvizice\n"
    r = client.post("/database/import", data={
        "csrf_token": csrf(client), "organization_id": str(org),
        "source_name": "List A", "mode": "import",
        "file": (io.BytesIO(rows.encode()), "akvizice.csv")},
        content_type="multipart/form-data")
    assert r.status_code == 302
    with Session(client.application.extensions["ema_engine"]) as db:
        contacts = db.scalars(select(Contact).where(Contact.email == "klient@example.cz")).all()
        assert len(contacts) == 1
        origins = db.scalars(select(ContactOrigin).where(
            ContactOrigin.contact_id == contacts[0].id)).all()
        assert len(origins) == 3
        assert sorted(x.source_kind for x in origins) == ["csv", "elementor_submissions", "users"]
    assert "klient@example.cz" in client.get("/database?kind=csv").get_data(as_text=True)
    assert "klient@example.cz" in client.get("/database?site=CSV%3A+akvizice").get_data(as_text=True)
    assert client.post(f"/database/sources/{sid}/sync", data={
        "csrf_token": csrf(client), "organization_id": str(client.application.ids["secret_org"])
    }).status_code == 302


def test_guest_cannot_list_or_read_company_contacts(web_client):
    client = web_client
    login(client, "guest")
    assert "klient@example.cz" not in client.get("/database").get_data(as_text=True)
    assert client.post("/database/sources", data={"csrf_token": csrf(client),
        "organization_id": str(client.application.ids["org"]),
        "site_url": "https://www.freshcrackers.cz",
        "accounting_read_key": "x"*64}).status_code == 403
    assert client.get("/database?org=" + str(client.application.ids["org"])).status_code == 403


def test_failed_sync_never_writes_partial_contacts(web_client, monkeypatch):
    client = web_client
    login(client, "owner")
    org = client.application.ids["org"]
    import ema.web as web
    client.application.config["MAIL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    monkeypatch.setattr(web, "canonical_site", lambda value: "https://www.freshcrackers.cz")
    monkeypatch.setattr(web, "fetch_page", lambda *a, **kw: {
        "kind": "users", "items": [], "next_after_id": 0, "has_more": False, "available": True})
    assert client.post("/database/sources", data={
        "csrf_token": csrf(client), "organization_id": str(org),
        "site_url": "https://www.freshcrackers.cz", "accounting_read_key": "r"*64
    }).status_code == 302
    with Session(client.application.extensions["ema_engine"]) as db:
        sid = db.scalar(select(FreshCoreSource.id))
    def broken(source, key, kind, *, after=0, limit=50):
        if kind == "elementor_submissions":
            raise FreshCoreError("Testovací chyba API")
        return {"kind": "users", "items": [_contact(1, email="rollback@example.cz")],
                "next_after_id": 1, "has_more": False, "available": True}
    monkeypatch.setattr(web, "fetch_page", broken)
    import ema.fresh_core_contacts as service
    monkeypatch.setattr(service, "fetch_page", broken)
    assert client.post(f"/database/sources/{sid}/sync",
                       data={"csrf_token": csrf(client)}).status_code == 302
    with Session(client.application.extensions["ema_engine"]) as db:
        assert db.scalar(select(Contact.id).where(Contact.email == "rollback@example.cz")) is None
        source = db.get(FreshCoreSource, sid)
        assert source.users_after_id == 0
        assert "Testovací chyba" in source.last_error


def test_contact_provenance_is_tenant_scoped_and_idempotent(web_client):
    app = web_client.application
    org = app.ids["org"]
    other = app.ids["secret_org"]
    with Session(app.extensions["ema_engine"]) as db:
        for oid in (org, other):
            result = ingest_contacts(db, oid, "https://www.example.cz", "users",
                                     [_contact(42)])
            assert result["created"] == 1
            result = ingest_contacts(db, oid, "https://www.example.cz", "users",
                                     [_contact(42)])
            assert result["created"] == 0
            db.commit()
        assert len(db.scalars(select(Contact).where(Contact.email == "klient@example.cz")).all()) == 2
        assert len(db.scalars(select(ContactOrigin)).all()) == 2
