"""HTTP test client scenarios run in GitHub Actions after installing requirements-dev.txt."""
import re
import pytest
from sqlalchemy import select
from werkzeug.security import generate_password_hash
from ema.web import create_app
from ema.models import Base, User, Organization, Membership, Project, ProjectGrant, Company, make_session


@pytest.fixture
def client(tmp_path):
    db_url = "sqlite:///" + str(tmp_path / "ema-test.sqlite")
    app = create_app({"TESTING": True, "DATABASE_URL": db_url, "SECRET_KEY": "test-only-secret", "SESSION_COOKIE_SECURE": False})
    Base.metadata.create_all(app.extensions["ema_engine"])
    engine, Factory = make_session(db_url)
    with Factory() as db:
        a = User(email="alice@example.cz", name="Alice", password_hash=generate_password_hash("a-password-12345"))
        b = User(email="bob@example.cz", name="Bob", password_hash=generate_password_hash("b-password-12345"))
        o = Organization(name="Fresh Crackers")
        db.add_all([a, b, o]);db.flush()
        db.add(Membership(organization_id=o.id, user_id=a.id, role="owner"))
        p = Project(organization_id=o.id, name="Obchodní projekt")
        db.add(p);db.flush()
        db.add(ProjectGrant(project_id=p.id, user_id=b.id, role="viewer"))
        db.commit()
    app.test_ids = dict(org=o.id, project=p.id)
    return app.test_client()


def csrf(client):
    with client.session_transaction() as s:
        return s["csrf"]


def login(client, email, password):
    client.get("/login")
    return client.post("/login", data={"csrf_token": csrf(client), "email": email, "password": password})


def test_health_login_and_csrf(client):
    assert client.get("/health").json["status"] == "ok"
    assert client.get("/").status_code == 302
    assert client.post("/login", data={"email": "alice@example.cz"}).status_code == 400
    assert login(client, "alice@example.cz", "a-password-12345").status_code == 302
    assert b"Fresh Crackers" in client.get("/").data


def test_project_guest_is_not_org_member(client):
    assert login(client, "bob@example.cz", "b-password-12345").status_code == 302
    ids = client.application.test_ids
    assert client.get(f"/project/{ids['project']}").status_code == 200
    assert client.get(f"/project/{ids['project']}/chat").status_code == 200
    assert client.get(f"/org/{ids['org']}/clients").status_code == 403
    assert client.post(f"/project/{ids['project']}/chat", data={"csrf_token": csrf(client), "body": "Viewer must not write"}).status_code == 403


def test_company_chat_is_persistent_and_scoped(client):
    assert login(client, "alice@example.cz", "a-password-12345").status_code == 302
    org_id = client.application.test_ids["org"]
    assert client.post(f"/org/{org_id}/chat", data={"csrf_token": csrf(client), "body": "Závazek pro klienta"}).status_code == 302
    assert "Závazek pro klienta".encode() in client.get(f"/org/{org_id}/chat").data
    assert "Závazek pro klienta".encode() not in client.get(f"/project/{client.application.test_ids['project']}/chat").data


def test_create_client_and_pipeline(client):
    assert login(client, "alice@example.cz", "a-password-12345").status_code == 302
    org = client.application.test_ids["org"]
    assert client.post(f"/org/{org}/clients", data={"csrf_token": csrf(client), "name": "ABC s.r.o."}).status_code == 302
    assert b"ABC s.r.o." in client.get(f"/org/{org}/clients").data
    assert client.post(f"/org/{org}/pipeline", data={"csrf_token": csrf(client), "title": "AI Audit"}).status_code == 302
    assert b"AI Audit" in client.get(f"/org/{org}/pipeline").data