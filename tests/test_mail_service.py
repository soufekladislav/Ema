from cryptography.fernet import Fernet
from ema.mail_service import encrypt_password, decrypt_password, parse_metadata, MailError, send_plain
import pytest


def test_password_encryption_roundtrip():
    key = Fernet.generate_key().decode()
    cipher = encrypt_password("SECRET-demo-password", key)
    assert "SECRET" not in cipher
    assert decrypt_password(cipher, key) == "SECRET-demo-password"


def test_metadata_parser_not_body():
    info = [(b'1 (UID 118 FLAGS (\\Seen) RFC822.SIZE 987 BODY[HEADER.FIELDS] {120}',
             b'From: "Klient" <client@example.cz>\r\nTo: info@example.cz\r\nSubject: =?utf-8?b?UHJvamVrdA==?=\r\nDate: Mon, 16 Nov 2026 12:05:00 +0100\r\nMessage-ID: <abc@example.cz>\r\n\r\n'), b')']
    row = parse_metadata(info, 118, 5, 6, 99)
    assert row.subject == "Projekt"
    assert row.uidvalidity == 99
    assert row.size_bytes == 987
    assert row.sender.startswith('Klient')


def test_header_injection_blocked(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr("ema.mail_service.validate_mail_host", lambda host: host)
    box = SimpleNamespace(smtp_host="smtp.example.cz", smtp_port=465,
                          username="u", credential="x", address="info@example.cz")
    with pytest.raises(MailError):
        send_plain(box, "key", "to@example.cz", "A\r\nBcc:secret@example.cz", "Hi")
def test_smtp_uses_separate_username(monkeypatch):
    from types import SimpleNamespace
    from cryptography.fernet import Fernet
    from ema.mail_service import encrypt_password
    used = {}
    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def login(self, username, password):
            used["username"] = username
            used["password"] = password
        def send_message(self, message):
            used["subject"] = message["Subject"]
    monkeypatch.setattr("ema.mail_service.validate_mail_host", lambda host: host)
    monkeypatch.setattr("ema.mail_service.smtplib.SMTP_SSL", FakeSMTP)
    key = Fernet.generate_key().decode("ascii")
    box = SimpleNamespace(smtp_host="smtp.example.cz", smtp_port=465,
                          username="imap@example.cz", smtp_username="smtp-other@example.cz",
                          credential=encrypt_password("test-password", key), address="info@example.cz")
    send_plain(box, key, "client@example.cz", "Test", "Text")
    assert used == {"username": "smtp-other@example.cz", "password": "test-password", "subject": "Test"}


def test_wrong_mailbox_fernet_key_reports_actionable_error_before_network(monkeypatch):
    from types import SimpleNamespace
    from ema.mail_service import _connect
    good_key = Fernet.generate_key().decode("ascii")
    wrong_key = Fernet.generate_key().decode("ascii")
    box = SimpleNamespace(imap_host="imap.example.cz", imap_port=993,
                          username="info@example.cz",
                          credential=encrypt_password("example-test-password", good_key))
    monkeypatch.setattr("ema.mail_service.validate_mail_host", lambda host: host)
    with pytest.raises(MailError, match="nelze rozšifrovat"):
        _connect(box, wrong_key)


def test_failed_imap_connection_persists_safe_mailbox_diagnostic(tmp_path, monkeypatch):
    from sqlalchemy.orm import Session
    from werkzeug.security import generate_password_hash
    from ema.models import Base, Mailbox, Organization, User, make_session
    from ema.mail_service import sync_inbox
    db_url = "sqlite:///" + str(tmp_path / "mail-sync-status.sqlite")
    engine, _ = make_session(db_url)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="test@example.cz", name="Test",
                    password_hash=generate_password_hash("test-long-password"))
        org = Organization(name="Test company")
        db.add_all([user, org])
        db.flush()
        box = Mailbox(organization_id=org.id, owner_id=user.id, label="Test",
                      address="info@example.cz", username="info@example.cz",
                      imap_host="imap.example.cz", smtp_host="smtp.example.cz",
                      credential="encrypted-placeholder")
        db.add(box)
        db.commit()
        box_id = box.id

        def fake_connection(box, key):
            raise MailError("IMAP server odmítl přihlášení.")
        monkeypatch.setattr("ema.mail_service._connect", fake_connection)
        with pytest.raises(MailError, match="odmítl přihlášení"):
            sync_inbox(db, box, "test-only", limit=10)

        db.expire_all()
        stored = db.get(Mailbox, box_id)
        assert stored.status == "error"
        assert stored.sync_error == "IMAP server odmítl přihlášení."
