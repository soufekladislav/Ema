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

def test_login_uses_legacy_php_hero_without_open_registration(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"https://www.freshcrackers.cz/wp-content/uploads/icons/ema-source.jpg" in response.data
    assert b"https://www.freshcrackers.cz/wp-content/uploads/2023/10/Fresh-Crackers-Logo.png" in response.data
    assert b'rel="icon" type="image/png"' in response.data
    assert "Emě stačí říct,".encode() in response.data
    assert b'name="csrf_token"' in response.data
    assert b'href="/register"' not in response.data
    assert "https://www.freshcrackers.cz" in response.headers["Content-Security-Policy"]


def test_project_index_is_primary_and_project_can_be_created(client):
    assert login(client, "alice@example.cz", "a-password-12345").status_code == 302
    org_id = client.application.test_ids["org"]
    start = client.get("/")
    assert b"Moje projekty" in start.data
    assert "Obchodní projekt".encode() in start.data
    assert b'name="organization_id"' in start.data
    created = client.post("/projects", data={
        "csrf_token": csrf(client), "organization_id": str(org_id),
        "name": "Pilotni zakazka", "description": "Vyvoj a obchod"
    })
    assert created.status_code == 302
    assert "/project/" in created.headers["Location"]
    assert b"Pilotni zakazka" in client.get("/").data
    project_html = client.get(created.headers["Location"]).data
    assert "Chat s Emou nad projektem".encode() in project_html
    assert b"Projekt" in project_html


def test_project_guest_can_navigate_own_project_not_company_or_other_projects(client):
    from sqlalchemy.orm import Session
    with Session(client.application.extensions["ema_engine"]) as db:
        other = Organization(name="Other private business")
        db.add(other)
        db.flush()
        secret = Project(organization_id=other.id, name="Secret private project")
        db.add(secret)
        db.flush()
        secret_id = secret.id
        db.commit()
    assert login(client, "bob@example.cz", "b-password-12345").status_code == 302
    data = client.get("/").data
    assert "Obchodní projekt".encode() in data
    assert b"Secret private project" not in data
    assert b"Klienti / CRM" not in data
    assert b'name="organization_id"' not in data
    org_id = client.application.test_ids["org"]
    response = client.post("/projects", data={
        "csrf_token": csrf(client), "organization_id": str(org_id), "name": "Not authorized"
    })
    assert response.status_code == 403
    assert client.get(f"/project/{secret_id}").status_code == 403


def test_hero_art_in_sidebar_and_project_chat(client):
    assert login(client, "alice@example.cz", "a-password-12345").status_code == 302
    project_id = client.application.test_ids["project"]
    index_html = client.get("/").data
    assert b'class="sidebar-hero"' in index_html
    assert b"icons/ema-source.jpg" in index_html
    assert b"2023/10/Fresh-Crackers-Logo.png" in index_html
    chat_html = client.get(f"/project/{project_id}/chat").data
    assert b'class="chat-hero-image"' in chat_html
    assert b'class="empty-state chat-empty-state"' in chat_html
    assert b"icons/ema-source.jpg" in chat_html


def test_assistant_home_is_primary_and_ai_is_explicitly_disabled(client):
    assert login(client, "alice@example.cz", "a-password-12345").status_code == 302
    html = client.get("/").data
    assert "Co dnes".encode() in html
    assert "Chat s Emou".encode() in html
    assert "AI zatím není připojena.".encode() in html
    assert b'/assistant' in html
    assert b'name="project_id"' in html


def test_assistant_conversation_uses_selected_project_and_persists_personally(client, monkeypatch):
    from ema.models import AssistantTurn
    assert login(client, "alice@example.cz", "a-password-12345").status_code == 302
    client.application.config.update(EMA_AI_ENGINE_API_KEY="test-engine-key", EMA_AI_ALLOWED_EMAILS="alice@example.cz")
    project_id = client.application.test_ids["project"]
    captured = {}
    def fake_engine(**kwargs):
        captured.update(kwargs)
        return "Prověřila jsem stav projektu. Nic jsem nezměnila."
    monkeypatch.setattr("ema.web.run_assistant", fake_engine)
    response = client.post("/assistant", data={
        "csrf_token": csrf(client), "project_id": str(project_id),
        "body": "Na čem pracujeme?"
    })
    assert response.status_code == 302
    assert "project=" in response.headers["Location"]
    assert captured["project_id"] == project_id
    assert [p.name for p in captured["projects"]] == ["Obchodní projekt"]
    result = client.get(response.headers["Location"])
    assert result.status_code == 200
    assert "Na čem pracujeme?".encode() in result.data
    assert "Nic jsem nezměnila.".encode() in result.data
    assert "Na čem pracujeme?".encode() not in client.get("/").data
    from sqlalchemy.orm import Session
    with Session(client.application.extensions["ema_engine"]) as db:
        turns = db.scalars(select(AssistantTurn).order_by(AssistantTurn.id)).all()
        assert [(t.role, t.user_id, t.project_id) for t in turns] == [
            ("user", 1, project_id), ("assistant", 1, project_id)]


def test_project_only_guest_cannot_prompt_ai_with_other_project_data(client, monkeypatch):
    assert login(client, "bob@example.cz", "b-password-12345").status_code == 302
    client.application.config.update(EMA_AI_ENGINE_API_KEY="test-engine-key", EMA_AI_ALLOWED_EMAILS="bob@example.cz")
    called = []
    monkeypatch.setattr("ema.web.run_assistant", lambda **kw: (called.append(kw) or "OK"))
    own = client.application.test_ids["project"]
    assert client.post("/assistant", data={
        "csrf_token": csrf(client), "project_id": "999999",
        "body": "Přečti mi cizí projekt"
    }).status_code == 403
    assert not called
    assert client.get("/?project=999999").status_code == 403
    assert client.get(f"/?project={own}").status_code == 200
    assert b"Klienti / CRM" not in client.get(f"/?project={own}").data


def test_schema_upgrade_restores_mailbox_columns_without_data_loss(tmp_path):
    from sqlalchemy import text, inspect
    from ema.schema_upgrade import upgrade_schema
    db_url = "sqlite:///" + str(tmp_path / "old-ema.sqlite")
    engine, _ = make_session(db_url)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        # Simulate the pre-PR65 mailbox table on an existing SQLite pilot DB.
        conn.execute(text("ALTER TABLE mailboxes DROP COLUMN smtp_username"))
        conn.execute(text("ALTER TABLE mailboxes DROP COLUMN signature_html"))
        conn.execute(text("INSERT INTO users (id,email,name,password_hash,active,superadmin,created_at) "
                          "VALUES (1,'legacy@example.cz','Legacy','hash',1,0,'2026-01-01')"))
        conn.execute(text("INSERT INTO organizations (id,name,active,created_at) VALUES (1,'Legacy org',1,'2026-01-01')"))
        conn.execute(text("INSERT INTO mailboxes (id,organization_id,owner_id,label,address,username,"
                          "imap_host,imap_port,smtp_host,smtp_port,credential,status,sync_error,created_at) "
                          "VALUES (1,1,1,'Mailbox','legacy@example.cz','legacy@example.cz',"
                          "'mail.example.cz',993,'mail.example.cz',465,'encrypted','not_synced','','2026-01-01')"))
    assert set(upgrade_schema(engine)) == {"mailboxes.smtp_username", "mailboxes.signature_html"}
    assert upgrade_schema(engine) == []
    with engine.begin() as conn:
        row = conn.execute(text("SELECT address,smtp_username,signature_html FROM mailboxes WHERE id=1")).one()
        assert row[0] == "legacy@example.cz"
        assert row[1] == ""
        assert row[2] == ""
    assert inspect(engine).has_table("assistant_turns")
