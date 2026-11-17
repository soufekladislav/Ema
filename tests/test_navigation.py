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


def test_project_pipeline_is_scoped_to_firm_and_project(web_client):
    client = web_client
    login(client, "owner")
    org_id = client.application.ids["org"]
    project_id = client.application.ids["project"]
    bad_project = client.application.ids["secret_project"]
    assert client.get(f"/org/{org_id}/pipeline?project={bad_project}").status_code == 403
    assert client.post(f"/org/{org_id}/pipeline", data={
        "csrf_token": csrf(client), "project_id": str(bad_project),
        "title": "Never cross companies"
    }).status_code == 400
    created = client.post(f"/org/{org_id}/pipeline", data={
        "csrf_token": csrf(client), "project_id": str(project_id),
        "title": "Offer for Ema"
    })
    assert created.status_code == 302
    assert f"project={project_id}" in created.headers["Location"]
    listing = client.get(f"/org/{org_id}/pipeline?project={project_id}")
    assert b"Offer for Ema" in listing.data
    project = client.get(f"/project/{project_id}")
    assert b"Offer for Ema" in project.data


def test_project_type_saved_and_invalid_category_rejected(web_client):
    client = web_client
    login(client, "owner")
    org_id = client.application.ids["org"]
    assert client.post("/projects", data={"csrf_token": csrf(client),
                      "organization_id": str(org_id), "name": "My shop",
                      "kind": "shop"}).status_code == 302
    assert client.post("/projects", data={"csrf_token": csrf(client),
                      "organization_id": str(org_id), "name": "invalid",
                      "kind": "unauthorized-type"}).status_code == 400
    with Session(client.application.extensions["ema_engine"]) as db:
        row = db.scalar(select(Project).where(Project.name == "My shop"))
        assert row.kind == "shop"
    assert "E-shop".encode() in client.get("/projects").data


def test_schema_upgrade_is_idempotent_for_project_kind_and_contact_metadata(tmp_path):
    from sqlalchemy import inspect, text
    from ema.schema_upgrade import upgrade_schema
    from ema.models import make_session
    url = "sqlite:///" + str(tmp_path / "old-schema.sqlite")
    engine, factory = make_session(url)
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("ALTER TABLE projects DROP COLUMN kind"))
        c.execute(text("ALTER TABLE contacts DROP COLUMN metadata_json"))
    changes = set(upgrade_schema(engine))
    assert changes == {"projects.kind", "contacts.metadata_json"}
    assert upgrade_schema(engine) == []
    inspector = inspect(engine)
    assert "kind" in {c["name"] for c in inspector.get_columns("projects")}
    assert "metadata_json" in {c["name"] for c in inspector.get_columns("contacts")}


def test_mail_hub_only_lists_authorized_company_mailboxes(web_client):
    client = web_client
    with Session(client.application.extensions["ema_engine"]) as db:
        o1 = client.application.ids["org"]
        o2 = client.application.ids["secret_org"]
        uid = client.application.ids["owner"]
        db.add_all([
            Mailbox(organization_id=o1, owner_id=uid, label="Owned mail",
                    address="owned@example.cz", username="owned@example.cz",
                    imap_host="mail.example.cz", smtp_host="smtp.example.cz",
                    credential="not-real"),
            Mailbox(organization_id=o2, owner_id=uid, label="Secret mailbox",
                    address="secret@example.cz", username="secret@example.cz",
                    imap_host="mail.example.cz", smtp_host="smtp.example.cz",
                    credential="not-real")
        ])
        db.commit()
    login(client, "owner")
    html = client.get("/mail").data
    assert b"owned@example.cz" in html
    assert b"secret@example.cz" not in html


def test_global_mail_sync_action_is_available_only_to_mailbox_managers(web_client, monkeypatch):
    from ema.models import now
    client = web_client
    with Session(client.application.extensions["ema_engine"]) as db:
        owned = Mailbox(organization_id=client.application.ids["org"],
                        owner_id=client.application.ids["owner"],
                        label="Pilot mail", address="pilot@example.cz",
                        username="pilot@example.cz", imap_host="imap.example.cz",
                        smtp_host="smtp.example.cz", credential="test-only")
        db.add(owned)
        db.commit()
        box_id = owned.id
    login(client, "owner")
    page = client.get(f"/mail?box={box_id}")
    assert page.status_code == 200
    assert "Aktualizovat 50 zpráv".encode() in page.data
    assert "Pošta zatím nesynchronizována".encode() in page.data
    captured = {}
    def fake_sync(db, box, key, limit):
        captured.update(mailbox_id=box.id, limit=limit)
        box.status, box.sync_error, box.last_sync = "ok", "", now()
        db.commit()
        return 3
    monkeypatch.setattr("ema.web.sync_inbox", fake_sync)
    result = client.post(f"/mail/{box_id}/sync", data={"csrf_token": csrf(client)})
    assert result.status_code == 302
    assert result.headers["Location"].endswith(f"/mail?box={box_id}")
    assert captured == {"mailbox_id": box_id, "limit": 10}
    success = client.get(result.headers["Location"])
    assert "Připojeno".encode() in success.data
    assert "načteno 3 nových zpráv".encode() in success.data
    # Project guests do not acquire access to company mail by being in a project.
    # Use a fresh client to avoid accidental reliance on the owner session.
    another = web_client.application.test_client()
    login(another, "guest")
    assert another.get(f"/mail?box={box_id}").status_code == 403
    assert another.post(f"/mail/{box_id}/sync",
                        data={"csrf_token": csrf(another)}).status_code == 403


def test_mailbox_order_visibility_and_personal_read_star_state(web_client):
    from ema.models import MailboxView, MailUserState
    client = web_client
    with Session(client.application.extensions["ema_engine"]) as db:
        owner = client.application.ids["owner"]
        org = client.application.ids["org"]
        b1 = Mailbox(organization_id=org, owner_id=owner, label="First Mail",
                     address="first@example.cz", username="first@example.cz",
                     imap_host="imap.example.cz", smtp_host="smtp.example.cz", credential="demo")
        b2 = Mailbox(organization_id=org, owner_id=owner, label="Second Mail",
                     address="second@example.cz", username="second@example.cz",
                     imap_host="imap.example.cz", smtp_host="smtp.example.cz", credential="demo")
        db.add_all([b1, b2])
        db.flush()
        folder = MailFolder(mailbox_id=b1.id, name="INBOX", uidvalidity=22)
        db.add(folder)
        db.flush()
        m1 = MailMessage(mailbox_id=b1.id, folder_id=folder.id, uidvalidity=22,
                         uid=101, sender="contact@example.cz", subject="Unread mail", flags="")
        m2 = MailMessage(mailbox_id=b1.id, folder_id=folder.id, uidvalidity=22,
                         uid=102, sender="contact@example.cz", subject="Already read",
                         flags=r"\Seen")
        db.add_all([m1, m2])
        db.commit()
        id1, id2, mid1, mid2 = b1.id, b2.id, m1.id, m2.id

    login(client, "owner")
    page = client.get("/mail")
    assert page.status_code == 200
    assert b"Unread mail" in page.data
    assert b"Already read" in page.data
    assert b"1</strong> nep" in page.data
    assert b'ema-mail-message-row is-unread' in page.data
    assert b'ema-mail-message-row is-read' in page.data

    order = client.post("/mail/order", json={"ids": [id2, id1]},
                        headers={"X-CSRF-Token": csrf(client)})
    assert order.status_code == 200
    html = client.get("/mail").data.decode("utf-8")
    assert html.index("Second Mail") < html.index("First Mail")
    with Session(client.application.extensions["ema_engine"]) as db:
        rows = db.scalars(select(MailboxView).where(MailboxView.user_id == client.application.ids["owner"])).all()
        assert {v.mailbox_id: v.position for v in rows} == {id2: 1, id1: 2}
    invalid = client.post("/mail/order", json={"ids": [id1, 66666]},
                          headers={"X-CSRF-Token": csrf(client)})
    assert invalid.status_code == 400

    hidden = client.post(f"/mail/{id1}/include", data={"csrf_token": csrf(client)})
    assert hidden.status_code == 302
    assert b"Unread mail" not in client.get("/mail").data
    assert b"Unread mail" in client.get(f"/mail?box={id1}").data
    client.post(f"/mail/{id1}/include", data={"csrf_token": csrf(client)})
    assert b"Unread mail" in client.get("/mail").data

    client.post(f"/mail/{mid1}/state", data={"csrf_token": csrf(client), "action": "star"})
    client.post(f"/mail/{mid1}/state", data={"csrf_token": csrf(client), "action": "read"})
    page = client.get(f"/mail?box={id1}")
    assert "★".encode() in page.data
    assert b"0</strong> nep" in page.data
    client.post(f"/mail/{mid2}/state", data={"csrf_token": csrf(client), "action": "unread"})
    assert b"1</strong> nep" in client.get("/mail").data
    with Session(client.application.extensions["ema_engine"]) as db:
        row = db.scalar(select(MailUserState).where(
            MailUserState.mail_id == mid1, MailUserState.user_id == client.application.ids["owner"]))
        assert row.read_override is True and row.starred is True

    guest = web_client.application.test_client()
    login(guest, "guest")
    assert guest.post(f"/mail/{id1}/include", data={"csrf_token": csrf(guest)}).status_code == 403
    assert guest.post(f"/mail/{mid1}/state",
                      data={"csrf_token": csrf(guest), "action": "star"}).status_code == 403


def test_mailbox_edit_preserves_secret_without_password_and_changes_smtp(web_client, monkeypatch):
    client = web_client
    with Session(client.application.extensions["ema_engine"]) as db:
        b = Mailbox(organization_id=client.application.ids["org"],
                    owner_id=client.application.ids["owner"],
                    label="Edit me", address="edit@example.cz", username="edit@example.cz",
                    smtp_username="edit@example.cz", imap_host="imap.example.cz",
                    smtp_host="smtp.example.cz", smtp_port=465,
                    credential="encrypted-original")
        db.add(b)
        db.commit()
        box_id = b.id

    login(client, "owner")
    get_result = client.get(f"/org/{client.application.ids['org']}/mail/{box_id}/edit")
    assert get_result.status_code == 200
    assert "Nechat prázdné".encode() in get_result.data
    monkeypatch.setattr("ema.web.validate_mail_host", lambda host: host)
    result = client.post(f"/org/{client.application.ids['org']}/mail/{box_id}/edit", data={
        "csrf_token": csrf(client), "label": "Renamed",
        "address": "edit@example.cz", "username": "edit@example.cz",
        "smtp_username": "different@example.cz", "imap_host": "imap.example.cz",
        "smtp_host": "smtp2.example.cz", "smtp_port": "587", "password": "",
    })
    assert result.status_code == 302
    with Session(client.application.extensions["ema_engine"]) as db:
        b = db.get(Mailbox, box_id)
        assert b.label == "Renamed" and b.smtp_port == 587
        assert b.smtp_username == "different@example.cz"
        assert b.credential == "encrypted-original"
    guest = web_client.application.test_client()
    login(guest, "guest")
    assert guest.get(f"/org/{client.application.ids['org']}/mail/{box_id}/edit").status_code == 403


def test_mail_detail_renders_capped_sanitized_html_and_image_opt_in(web_client, monkeypatch):
    from ema.mail_render import MailPreview
    client = web_client
    with Session(client.application.extensions["ema_engine"]) as db:
        b = Mailbox(organization_id=client.application.ids["org"],
                    owner_id=client.application.ids["owner"],
                    label="HTML Mail", address="html@example.cz", username="html@example.cz",
                    imap_host="imap.example.cz", smtp_host="smtp.example.cz",
                    credential="encrypted-original")
        db.add(b)
        db.flush()
        folder = MailFolder(mailbox_id=b.id, name="INBOX", uidvalidity=90)
        db.add(folder)
        db.flush()
        mail = MailMessage(mailbox_id=b.id, folder_id=folder.id, uidvalidity=90,
                           uid=10, sender="sender@example.cz", subject="HTML content", flags="")
        db.add(mail)
        db.commit()
        id_box, id_mail = b.id, mail.id

    seen = []
    def fake_preview(box, msg, key, *, show_images=False, folder_name="INBOX"):
        seen.append(show_images)
        return MailPreview("<p>Read-only HTML</p>", "Plain", True, True, False)
    monkeypatch.setattr("ema.web.preview_message", fake_preview)
    login(client, "owner")
    url = f"/org/{client.application.ids['org']}/mail/message/{id_mail}"
    base = client.get(url)
    assert base.status_code == 200
    assert b"srcdoc=" in base.data
    assert "Načíst obrázky".encode() in base.data
    assert client.get(url + "?images=1").status_code == 200
    assert seen == [False, True]
    with Session(client.application.extensions["ema_engine"]) as db:
        from ema.models import MailUserState
        stored = db.scalar(select(MailUserState).where(MailUserState.mail_id == id_mail))
        assert stored.read_override is True
    assert "img-src".encode() in client.get(url + "?images=1").headers["Content-Security-Policy"].encode()


def test_mail_folder_view_has_50_refresh_and_folder_scroll_api(web_client, monkeypatch):
    client = web_client
    org = client.application.ids["org"]
    owner = client.application.ids["owner"]
    with Session(client.application.extensions["ema_engine"]) as db:
        box = Mailbox(organization_id=org, owner_id=owner, label="Folders",
                      address="folder@example.cz", username="folder@example.cz",
                      imap_host="imap.example.cz", smtp_host="smtp.example.cz", credential="none")
        db.add(box)
        db.flush()
        folder = MailFolder(mailbox_id=box.id, name="INBOX", uidvalidity=44)
        db.add(folder)
        db.commit()
        box_id, folder_id = box.id, folder.id
    login(client, "owner")
    page = client.get(f"/mail?box={box_id}")
    assert page.status_code == 200
    assert b"ema-mail-scrollpanel" in page.data
    assert "Aktualizovat 50 zpráv".encode() in page.data
    assert b"ema-folder-select" in page.data
    captured = {}
    def fake_page(db, box, key, folder, *, before_uid=None, limit=50):
        captured.update(box=box.id, folder=folder.id, cursor=before_uid, limit=limit)
        old = db.scalar(select(MailMessage).where(MailMessage.mailbox_id == box.id))
        if old is None:
            db.add(MailMessage(mailbox_id=box.id, folder_id=folder.id, uidvalidity=44,
                               uid=100, subject="New header", sender="sender@example.cz"))
            db.commit()
        return {"uids": [100], "has_more": False, "cursor": 100,
                "uidvalidity": 44, "server_total": 1}
    monkeypatch.setattr("ema.web.fetch_folder_page", fake_page)
    result = client.post(f"/mail/{box_id}/page", json={"folder_id": folder_id,
                          "before_uid": None}, headers={"X-CSRF-Token": csrf(client)})
    assert result.status_code == 200
    assert result.json["has_more"] is False
    assert b"New header" in result.json["html"].encode()
    assert captured == {"box": box_id, "folder": folder_id, "cursor": None, "limit": 50}
    assert client.post(f"/mail/{box_id}/page", json={"folder_id": 99999,
                       "before_uid": None}, headers={"X-CSRF-Token": csrf(client)}).status_code == 403
    wrong = web_client.application.test_client()
    login(wrong, "guest")
    assert wrong.post(f"/mail/{box_id}/page", json={"folder_id": folder_id,
                        "before_uid": None}, headers={"X-CSRF-Token": csrf(wrong)}).status_code == 403


def test_archive_and_trash_have_confirmation_and_scope(web_client, monkeypatch):
    from ema.models import MailMessage
    client = web_client
    org = client.application.ids["org"]
    owner = client.application.ids["owner"]
    with Session(client.application.extensions["ema_engine"]) as db:
        box = Mailbox(organization_id=org, owner_id=owner, label="Mailbox",
                      address="move@example.cz", username="move@example.cz",
                      imap_host="imap.example.cz", smtp_host="smtp.example.cz", credential="none")
        db.add(box)
        db.flush()
        inbox = MailFolder(mailbox_id=box.id, name="INBOX", uidvalidity=90)
        trash = MailFolder(mailbox_id=box.id, name="Trash", special_use=r"\Trash", uidvalidity=91)
        db.add_all([inbox, trash])
        db.flush()
        msg = MailMessage(mailbox_id=box.id, folder_id=inbox.id, uidvalidity=90,
                          uid=15, subject="Don't lose this", sender="sender@example.cz")
        db.add(msg)
        db.commit()
        mail_id, trash_id = msg.id, trash.id
    login(client, "owner")
    confirm = client.get(f"/mail/{mail_id}/move/confirm?action=trash")
    assert confirm.status_code == 200
    assert "Přesunout do Koše".encode() in confirm.data
    assert client.post(f"/mail/{mail_id}/move", data={"csrf_token": csrf(client),
                       "action": "trash"}).status_code == 400
    called = []
    def fake_move(db, box, key, msg, action):
        called.append(action)
        msg.moved = True
        db.commit()
        return db.get(MailFolder, trash_id)
    monkeypatch.setattr("ema.web.move_message", fake_move)
    done = client.post(f"/mail/{mail_id}/move", data={"csrf_token": csrf(client),
                       "action": "trash", "confirm": "yes"})
    assert done.status_code == 302
    assert called == ["trash"]
    with Session(client.application.extensions["ema_engine"]) as db:
        assert db.get(MailMessage, mail_id).moved
    guest = web_client.application.test_client()
    login(guest, "guest")
    assert guest.get(f"/mail/{mail_id}/move/confirm?action=trash").status_code == 404


def test_schema_upgrade_preserves_old_mail_folder_and_message_rows(tmp_path):
    from sqlalchemy import text, inspect
    from ema.schema_upgrade import upgrade_schema
    from ema.models import make_session
    engine, _ = make_session("sqlite:///" + str(tmp_path / "legacy-mail.sqlite"))
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE mail_folders DROP COLUMN special_use"))
        conn.execute(text("ALTER TABLE mail_folders DROP COLUMN delimiter"))
        conn.execute(text("ALTER TABLE mail_messages DROP COLUMN moved"))
    changes = set(upgrade_schema(engine))
    assert {"mail_folders.special_use", "mail_folders.delimiter", "mail_messages.moved"} <= changes
    assert upgrade_schema(engine) == []
    assert "moved" in {col["name"] for col in inspect(engine).get_columns("mail_messages")}
