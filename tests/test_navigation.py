"""Live Flask route tests for fixed menu, tenant isolation, empty admin setup and CSV import."""
import io
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from ema.models import (Base, User, Organization, Membership, Project, ProjectGrant,
                        Mailbox, MailMessage, MailFolder, Company, Contact, Task)
from ema.web import create_app


@pytest.fixture
def web_client(tmp_path):
    db_url = "sqlite:///" + str(tmp_path / "ema-nav-test.sqlite")
    app = create_app({"TESTING": True, "DATABASE_URL": db_url,
                      "SECRET_KEY": "unit-only-key", "SESSION_COOKIE_SECURE": False})
    Base.metadata.create_all(app.extensions["ema_engine"])
    with Session(app.extensions["ema_engine"]) as db:
        admin = User(email="admin@example.cz", name="Admin", superadmin=True,
                     password_hash=generate_password_hash("secure-password-a"))
        guest = User(email="guest@example.cz", name="Guest",
                     password_hash=generate_password_hash("secure-password-b"))
        owner = User(email="owner@example.cz", name="Owner",
                     password_hash=generate_password_hash("secure-password-c"))
        o1 = Organization(name="Fresh Online")
        o2 = Organization(name="Fresh Develop")
        db.add_all([admin, guest, owner, o1, o2])
        db.flush()
        db.add(Membership(user_id=owner.id, organization_id=o1.id, role="owner"))
        p1 = Project(organization_id=o1.id, name="Ema app")
        p2 = Project(organization_id=o2.id, name="Secret project")
        db.add_all([p1, p2])
        db.flush()
        db.add(ProjectGrant(user_id=guest.id, project_id=p1.id, role="viewer"))
        db.add_all([
            Company(organization_id=o1.id, name="Client visible"),
            Company(organization_id=o2.id, name="Client secret"),
            Task(organization_id=o1.id, project_id=p1.id, title="Assigned project task",
                 due_at=datetime.utcnow()+timedelta(days=1)),
            Task(organization_id=o1.id, title="Company-only secret task"),
            Task(organization_id=o2.id, project_id=p2.id, title="Other company task")
        ])
        db.commit()
        app.ids = {"admin": admin.id, "guest": guest.id, "owner": owner.id,
                   "org": o1.id, "secret_org": o2.id, "project": p1.id, "secret_project": p2.id}
    return app.test_client()


def login(client, name):
    client.get("/login")
    with client.session_transaction() as session:
        token = session["csrf"]
    response = client.post("/login", data={
        "csrf_token": token, "email": f"{name}@example.cz",
        "password": {"admin":"secure-password-a", "guest":"secure-password-b",
                    "owner":"secure-password-c"}[name]})
    assert response.status_code == 302


def csrf(client):
    with client.session_transaction() as session:
        return session["csrf"]


def test_first_admin_can_create_company_and_then_project(web_client):
    client = web_client
    login(client, "admin")
    account = client.get("/account")
    assert account.status_code == 200
    assert "Založit první firmu".encode() in account.data
    home = client.get("/")
    assert "Nejdřív založíme první firmu".encode() in home.data
    created = client.post("/organizations", data={"csrf_token": csrf(client), "name": "Cajna Cars"})
    assert created.status_code == 302
    assert created.headers["Location"].endswith("/account")
    assert b"Cajna Cars" in client.get("/account").data
    with Session(client.application.extensions["ema_engine"]) as db:
        organization = db.scalar(select(Organization).where(Organization.name == "Cajna Cars"))
        admin_id = client.application.ids["admin"]
        assert db.scalar(select(Membership).where(Membership.organization_id == organization.id,
                                                 Membership.user_id == admin_id)).role == "owner"
        org_id = organization.id
    result = client.post("/projects", data={"csrf_token": csrf(client),
                                          "name": "New assigned campaign", "organization_id": str(org_id)})
    assert result.status_code == 302
    assert b"New assigned campaign" in client.get("/projects").data


def test_fixed_global_menu_and_firm_filter_cannot_expand_access(web_client):
    client = web_client
    login(client, "owner")
    home = client.get("/")
    for text in ["Chat / Nástěnka", "E-maily", "Projekty", "Databáze / CRM",
                 "Úkoly / Plánovač", "Nastavení účtu"]:
        assert text.encode() in home.data
    assert b'name="firm"' in home.data
    assert client.get("/projects").status_code == 200
    assert client.get("/database").status_code == 200
    assert client.get("/mail").status_code == 200
    assert client.get("/tasks").status_code == 200
    forbidden = client.post("/account/scope", data={"csrf_token": csrf(client),
                                                    "firm": str(client.application.ids["secret_org"])})
    assert forbidden.status_code == 403
    accepted = client.post("/account/scope", data={"csrf_token": csrf(client),
                                                    "firm": str(client.application.ids["org"])})
    assert accepted.status_code == 302
    assert b"Client visible" in client.get("/database").data
    assert b"Client secret" not in client.get("/database").data


def test_project_guest_has_project_task_but_no_company_database_or_mailboxes(web_client):
    client = web_client
    login(client, "guest")
    assert b"Ema app" in client.get("/projects").data
    assert b"Secret project" not in client.get("/projects").data
    tasks = client.get("/tasks")
    assert tasks.status_code == 200
    assert b"Assigned project task" in tasks.data
    assert b"Company-only secret task" not in tasks.data
    assert b"Other company task" not in tasks.data
    assert b"Client visible" not in client.get("/database").data
    assert b"Client secret" not in client.get("/database").data
    assert b"name=\"organization_id\"" not in client.get("/projects").data
    assert client.get("/mail").status_code == 200
    assert client.post("/tasks/1/toggle", data={"csrf_token": csrf(client)}).status_code == 403


def test_csv_import_dry_run_metadata_dedupe_and_tenant_guard(web_client):
    client = web_client
    login(client, "owner")
    org = client.application.ids["org"]
    rows = "Jméno;E-mail;Telefon;Firma;Zdroj;Kampaň\nJana Novakova;jana@example.cz;777123123;Client visible;linkedin;pilot\n"
    def upload(mode, target=org):
        return client.post("/database/import", data={
            "csrf_token": csrf(client), "mode": mode,
            "organization_id": str(target),
            "file": (io.BytesIO(rows.encode("utf-8")), "test.csv")
        }, content_type="multipart/form-data")
    assert upload("preview").status_code == 302
    with Session(client.application.extensions["ema_engine"]) as db:
        assert db.scalar(select(Contact.id).where(Contact.email == "jana@example.cz")) is None
    assert upload("import").status_code == 302
    assert upload("import").status_code == 302
    with Session(client.application.extensions["ema_engine"]) as db:
        records = db.scalars(select(Contact).where(Contact.email == "jana@example.cz")).all()
        assert len(records) == 1
        assert records[0].organization_id == org
        assert records[0].company_id is not None
        meta = json.loads(records[0].metadata_json)
        assert meta["fields"]["zdroj"] == "linkedin"
        assert meta["fields"]["kampan"] == "pilot"
    assert upload("import", client.application.ids["secret_org"]).status_code == 403
