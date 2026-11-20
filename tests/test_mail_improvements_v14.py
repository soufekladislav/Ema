"""EMA Mail V1.4: newsletter fidelity, remote IMAP folders and mobile navigation."""
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from ema.mail_render import make_preview
from ema.mail_folders import create_server_folder, encode_modified_utf7, decode_modified_utf7
from ema.mail_service import MailError
from ema.models import MailFolder, MailFolderView, Mailbox
from tests.test_navigation import web_client, login, csrf


def test_newsletter_safe_button_css_survives_adjacent_remote_background():
    msg = EmailMessage()
    msg.set_content("Plain")
    msg.add_alternative("""
    <html><head><style>
      .cta { background-image:url("https://tracker.example.test/open.png");
             background-color:#078819; color:#fff; padding:18px; }
    </style></head><body>
      <table><tr><td class="cta" style="padding:16px;
        background-image:url('https://tracker.example.test/hidden.jpg');
        background-color:#078819;border-radius:6px">
        <a href="https://example.test/offer">KRYCÍ BARVY</a>
      </td></tr></table>
    </body></html>""", subtype="html")
    output = make_preview(msg.as_bytes())
    assert output.is_html
    assert ".cta{" in output.srcdoc
    assert "background-color:#078819" in output.srcdoc
    assert "padding:16px" in output.srcdoc
    assert "KRYCÍ BARVY" in output.srcdoc
    assert "tracker.example.test" not in output.srcdoc
    assert "<script" not in output.srcdoc


def test_modified_utf7_encode_and_remote_folder_create_is_server_first(monkeypatch, tmp_path):
    from ema.models import Base, User, Organization, make_session
    from werkzeug.security import generate_password_hash
    engine, _ = make_session("sqlite:///" + str(tmp_path / "folder.sqlite"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="mail@example.cz", name="Mail", password_hash=generate_password_hash("strong-password"))
        org = Organization(name="Org")
        db.add_all([user, org])
        db.flush()
        box = Mailbox(organization_id=org.id, owner_id=user.id,
                      label="Mail", address="mail@example.cz", username="mail@example.cz",
                      imap_host="mail.example.cz", smtp_host="smtp.example.cz", credential="not-real")
        db.add(box)
        db.commit()
        box_id = box.id

    class Fake:
        def __init__(self):
            self.names = ["INBOX"]
            self.created = []
        def list(self):
            return "OK", [rb'(\HasNoChildren) "/" "' + name.encode() + b'"' for name in self.names]
        def create(self, encoded):
            self.created.append(encoded)
            self.names.append(encoded.strip('"'))
            return "OK", [b"created"]
        def logout(self):
            pass

    fake = Fake()
    monkeypatch.setattr("ema.mail_folders._connect", lambda box, key: fake)
    assert decode_modified_utf7(encode_modified_utf7("Příležitosti & obchod")) == "Příležitosti & obchod"
    with Session(engine) as db:
        box = db.get(Mailbox, box_id)
        folder = create_server_folder(db, box, "key", "Příležitosti & obchod")
        assert folder is not None
        assert fake.created and fake.created[0].startswith('"')
        assert decode_modified_utf7(folder.name) == "Příležitosti & obchod"
        assert len(db.scalars(select(MailFolder)).all()) == 2
        from pytest import raises
        with raises(MailError):
            create_server_folder(db, box, "key", "INBOX")
        with raises(MailError):
            create_server_folder(db, box, "key", "a/b")
        assert len(fake.created) == 1


def test_folder_display_order_is_scoped_to_owner_and_does_not_move_imap(web_client, monkeypatch):
    client = web_client
    with Session(client.application.extensions["ema_engine"]) as db:
        b = Mailbox(organization_id=client.application.ids["org"],
                    owner_id=client.application.ids["owner"],
                    label="Owner box", address="box@example.cz", username="box@example.cz",
                    imap_host="imap.example.cz", smtp_host="smtp.example.cz", credential="key")
        db.add(b)
        db.flush()
        fs = [MailFolder(mailbox_id=b.id, name=name) for name in ("INBOX", "Clients", "Projects")]
        db.add_all(fs)
        db.commit()
        bid, fids = b.id, [f.id for f in fs]
    login(client, "owner")
    assert "Nová složka na serveru" in client.get(f"/mail?box={bid}").get_data(as_text=True)
    post = client.post(f"/mail/{bid}/folders/order",
                       json={"ids":[fids[2], fids[0], fids[1]]},
                       headers={"X-CSRF-Token":csrf(client)})
    assert post.status_code == 200, post.data
    assert post.json["ok"] and post.json["ids"][0] == fids[2]
    listing = client.get(f"/mail?box={bid}").get_data(as_text=True)
    assert listing.index(f'data-folder-id="{fids[2]}"') < listing.index(f'data-folder-id="{fids[0]}"')
    assert client.post(f"/mail/{bid}/folders/order",
                       json={"ids":[fids[0], fids[0], fids[2]]},
                       headers={"X-CSRF-Token":csrf(client)}).status_code == 400
    with Session(client.application.extensions["ema_engine"]) as db:
        rows = db.scalars(select(MailFolderView).where(MailFolderView.mailbox_id == bid)).all()
        assert len(rows) == 3
        assert all(row.user_id == client.application.ids["owner"] for row in rows)
        assert len(db.scalars(select(MailFolder)).all()) == 3
    # Project-only user never gains mailbox access through project membership.
    client.post("/logout", data={"csrf_token":csrf(client)})
    login(client, "guest")
    assert client.post(f"/mail/{bid}/folders/order",
                       json={"ids":fids}, headers={"X-CSRF-Token":csrf(client)}).status_code == 403
    assert client.post(f"/mail/{bid}/folders/create", data={
        "csrf_token":csrf(client), "name":"Secret"}).status_code == 403


def test_mobile_bottom_bar_matches_real_pages_only_when_logged_in(web_client):
    client = web_client
    assert b"ema-mobile-bottom-nav" not in client.get("/login").data
    login(client, "owner")
    for path in ("/", "/mail", "/projects", "/tasks", "/database", "/account"):
        data = client.get(path).get_data(as_text=True)
        assert "ema-mobile-bottom-nav" in data
        assert "ema-mobile-bottom-v1.css" in data
        assert "mail-folder-order-v1.js" in data
        assert 'data-ema-mobile-more' in data
