"""IMAP 50-item pagination and safe MOVE tests; never call a real mail server."""
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from ema.models import Base, Mailbox, MailFolder, MailMessage, Organization, User, make_session
from ema.mail_folders import (
    parse_list_line, decode_modified_utf7, discover_folders,
    fetch_folder_page, move_message, special_folder,
)
from ema.mail_service import MailError


class FakeImap:
    capabilities = (b"IMAP4rev1", b"MOVE", b"UIDPLUS")

    def __init__(self, count=125):
        self.count = count
        self.selected = "INBOX"
        self.moved = []

    def list(self):
        return "OK", [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren \\All) "/" "[Gmail]/All Mail"',
            b'(\\HasNoChildren \\Trash) "/" "[Gmail]/Trash"',
            b'(\\HasNoChildren) "/" "Work"',
        ]

    def select(self, folder, readonly=True):
        self.selected = folder
        return "OK", [str(self.count).encode()]

    def response(self, name):
        assert name == "UIDVALIDITY"
        return "UIDVALIDITY", [b"333"]

    def uid(self, action, *args):
        if action == "SEARCH":
            return "OK", [b" ".join(str(n).encode() for n in range(1, self.count + 1))]
        if action == "FETCH":
            numbers = [int(x) for x in args[0].split(",")]
            result = []
            for uid in numbers:
                result.append((f"1 (UID {uid} FLAGS (\\Seen) RFC822.SIZE 200 BODY[HEADER.FIELDS] {{130}}".encode(),
                    (f"From: Inbox <test@example.cz>\r\nTo: pilot@example.cz\r\n"
                     f"Subject: Test item {uid}\r\nDate: Tue, 17 Nov 2026 10:01:00 +0100\r\n"
                     f"Message-ID: <test-{uid}@example.cz>\r\n\r\n").encode()))
            return "OK", result
        if action == "MOVE":
            self.moved.append((args[0], args[1]))
            return "OK", [b""]
        raise AssertionError(action)

    def logout(self):
        return "BYE", [b"ok"]


@pytest.fixture
def state(tmp_path):
    engine, _ = make_session("sqlite:///" + str(tmp_path / "emails.sqlite"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        u = User(name="Demo", email="demo@example.cz",
                 password_hash=generate_password_hash("demo-test-password"))
        org = Organization(name="Company")
        db.add_all([u, org])
        db.flush()
        box = Mailbox(organization_id=org.id, owner_id=u.id,
                      label="Mailbox", address="pilot@example.cz",
                      username="pilot@example.cz", imap_host="imap.example.cz",
                      smtp_host="smtp.example.cz", credential="encrypted-demo")
        db.add(box)
        db.flush()
        folder = MailFolder(mailbox_id=box.id, name="INBOX")
        db.add(folder)
        db.commit()
        return engine, box.id, folder.id


def test_folder_list_parsing_and_modified_utf7():
    assert parse_list_line(b'(\\Trash \\HasNoChildren) "/" "[Gmail]/Trash"') == (
        "[Gmail]/Trash", r"\Trash \HasNoChildren", "/")
    assert parse_list_line(b'(\\Noselect) "/" "disabled"') is None
    assert parse_list_line(b'(\\HasNoChildren) "/" "../escape"') is not None
    assert decode_modified_utf7("Sales &- Marketing") == "Sales & Marketing"


def test_last_50_then_50_then_25_do_not_remove_server_mail(state, monkeypatch):
    engine, box_id, inbox_id = state
    fake = FakeImap(count=125)
    monkeypatch.setattr("ema.mail_folders._connect", lambda box, key: fake)
    with Session(engine) as db:
        box, folder = db.get(Mailbox, box_id), db.get(MailFolder, inbox_id)
        first = fetch_folder_page(db, box, "key", folder)
        assert len(first["uids"]) == 50 and first["uids"][0] == 76
        assert first["has_more"] and first["cursor"] == 76
        second = fetch_folder_page(db, box, "key", folder, before_uid=first["cursor"])
        assert len(second["uids"]) == 50 and second["uids"][0] == 26
        third = fetch_folder_page(db, box, "key", folder, before_uid=second["cursor"])
        assert len(third["uids"]) == 25 and not third["has_more"]
        assert db.scalar(select(MailFolder).where(MailFolder.id == inbox_id)).uidvalidity == 333
        assert len(db.scalars(select(MailMessage).where(MailMessage.mailbox_id == box_id)).all()) == 125
        assert box.server_message_count == 125
        # Re-request latest headers: no duplicate messages.
        fetch_folder_page(db, box, "key", folder)
        assert len(db.scalars(select(MailMessage).where(MailMessage.mailbox_id == box_id)).all()) == 125
        assert len(fake.moved) == 0


def test_archive_and_trash_require_special_use_and_move_without_expunge(state, monkeypatch):
    engine, box_id, inbox_id = state
    fake = FakeImap(count=5)
    monkeypatch.setattr("ema.mail_folders._connect", lambda box, key: fake)
    with Session(engine) as db:
        box, folder = db.get(Mailbox, box_id), db.get(MailFolder, inbox_id)
        discover_folders(db, box, "key")
        assert special_folder(db, box, "trash").name == "[Gmail]/Trash"
        assert special_folder(db, box, "archive").name == "[Gmail]/All Mail"
        fetch_folder_page(db, box, "key", folder)
        mail = db.scalar(select(MailMessage).where(MailMessage.uid == 5))
        destination = move_message(db, box, "key", mail, "trash")
        assert destination.name == "[Gmail]/Trash"
        assert fake.moved == [("5", '"[Gmail]/Trash"')]
        assert mail.moved is True
        # A second click must not move again.
        with pytest.raises(MailError):
            move_message(db, box, "key", mail, "archive")
        assert len(fake.moved) == 1


def test_no_move_extension_must_not_delete_or_expunge(state, monkeypatch):
    engine, box_id, inbox_id = state
    fake = FakeImap(count=2)
    fake.capabilities = (b"IMAP4rev1",)
    monkeypatch.setattr("ema.mail_folders._connect", lambda box, key: fake)
    with Session(engine) as db:
        box, folder = db.get(Mailbox, box_id), db.get(MailFolder, inbox_id)
        discover_folders(db, box, "key")
        fetch_folder_page(db, box, "key", folder)
        mail = db.scalar(select(MailMessage).where(MailMessage.uid == 2))
        with pytest.raises(MailError, match="UID MOVE"):
            move_message(db, box, "key", mail, "trash")
        assert not fake.moved
        assert not mail.moved
