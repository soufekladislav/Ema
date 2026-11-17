"""IMAP 50-item pagination and safe MOVE tests; never call a real mail server."""
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from ema.models import Base, Mailbox, MailFolder, MailMessage, Organization, User, make_session
from ema.mail_folders import (
    parse_list_line, decode_modified_utf7, discover_folders,
    fetch_folder_page, move_message, move_many_messages, empty_trash_batch,
    append_sent_copy, special_folder, preview_trash_all, empty_trash_all,
)
from ema.mail_service import MailError


class FakeImap:
    capabilities = (b"IMAP4rev1", b"MOVE", b"UIDPLUS")

    def __init__(self, count=125):
        self.count = count
        self.selected = "INBOX"
        self.moved = []
        self.deleted = []
        self.uid_expunge = []
        self.full_expunge = 0
        self.appended = []
        self.copied = []

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
        if action == "COPY":
            self.copied.append((args[0], args[1]))
            return "OK", [b""]
        if action == "STORE":
            self.deleted.append((args[0], args[1], args[2]))
            return "OK", [b""]
        if action == "EXPUNGE":
            self.uid_expunge.append(args[0])
            return "OK", [b""]
        raise AssertionError(action)

    def expunge(self):
        self.full_expunge += 1
        return "OK", [b"1"]

    def append(self, name, flags, when, content):
        self.appended.append((name, flags, content))
        return "OK", [b"APPENDUID 333 77"]

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
        target = move_message(db, box, "key", mail, "trash")
        assert target.name == "[Gmail]/Trash"
        assert not fake.moved
        assert fake.copied == [("2", '"[Gmail]/Trash"')]
        assert fake.deleted == [("2", "+FLAGS.SILENT", r"(\Deleted)")]
        assert not fake.uid_expunge
        assert mail.moved



def test_single_uil_move_batch_and_folder_name_with_dot_separator(state, monkeypatch):
    engine, box_id, inbox_id = state
    fake = FakeImap(count=3)
    fake.list = lambda: ("OK", [
        rb'(\HasNoChildren) "." "INBOX"',
        rb'(\HasNoChildren) "." "INBOX.Trash"',
        rb'(\HasNoChildren) "." "INBOX.Sent"',
    ])
    monkeypatch.setattr("ema.mail_folders._connect", lambda box, key: fake)
    with Session(engine) as db:
        box, inbox = db.get(Mailbox, box_id), db.get(MailFolder, inbox_id)
        discover_folders(db, box, "key")
        assert special_folder(db, box, "trash").name == "INBOX.Trash"
        assert special_folder(db, box, "sent").name == "INBOX.Sent"
        fetch_folder_page(db, box, "key", inbox)
        rows = db.scalars(select(MailMessage).order_by(MailMessage.uid)).all()
        destination = move_many_messages(db, box, "key", rows, "trash")
        assert destination.name == "INBOX.Trash"
        assert fake.moved == [("1,2,3", '"INBOX.Trash"')]
        assert all(m.moved for m in rows)


def test_empty_trash_requires_uidplus_and_targeted_expunge(state, monkeypatch):
    engine, box_id, inbox_id = state
    fake = FakeImap(count=4)
    monkeypatch.setattr("ema.mail_folders._connect", lambda box, key: fake)
    with Session(engine) as db:
        box = db.get(Mailbox, box_id)
        discover_folders(db, box, "key")
        trash = special_folder(db, box, "trash")
        deleted, more = empty_trash_batch(db, box, "key", trash)
        assert (deleted, more) == (4, False)
        assert fake.deleted == [("1,2,3,4", "+FLAGS.SILENT", r"(\Deleted)")]
        assert fake.uid_expunge == ["1,2,3,4"]
        fake.capabilities = (b"IMAP4rev1", b"MOVE")
        deleted_legacy, remaining = empty_trash_batch(db, box, "key", trash)
        assert (deleted_legacy, remaining) == (4, False)
        assert fake.full_expunge == 1
        assert len(fake.uid_expunge) == 1


def test_sent_append_uses_discovered_real_folder(state, monkeypatch):
    engine, box_id, inbox_id = state
    fake = FakeImap(count=2)
    fake.list = lambda: ("OK", [
        rb'(\HasNoChildren) "/" "INBOX"',
        rb'(\HasNoChildren \Sent) "/" "Sent"',
    ])
    monkeypatch.setattr("ema.mail_folders._connect", lambda box, key: fake)
    with Session(engine) as db:
        box = db.get(Mailbox, box_id)
        destination = append_sent_copy(db, box, "key", b"Subject: test\r\n\r\nHello")
        assert destination.name == "Sent"
        assert fake.appended == [('"Sent"', r"(\Seen)", b"Subject: test\r\n\r\nHello")]



def test_legacy_imap_bulk_copy_flags_only_selected_without_expunge(state, monkeypatch):
    engine, box_id, inbox_id = state
    fake = FakeImap(count=4)
    fake.capabilities = (b"IMAP4rev1",)
    monkeypatch.setattr("ema.mail_folders._connect", lambda box, key: fake)
    with Session(engine) as db:
        box, inbox = db.get(Mailbox, box_id), db.get(MailFolder, inbox_id)
        discover_folders(db, box, "key")
        fetch_folder_page(db, box, "key", inbox)
        messages = db.scalars(select(MailMessage).where(MailMessage.uid.in_([2, 4]))).all()
        target = move_many_messages(db, box, "key", messages, "trash")
        assert target.name == "[Gmail]/Trash"
        assert fake.copied == [("2,4", '"[Gmail]/Trash"')]
        assert fake.deleted == [("2,4", "+FLAGS.SILENT", r"(\Deleted)")]
        assert not fake.uid_expunge
        assert all(m.moved for m in messages)


def test_legacy_copy_store_failure_marks_remote_result_uncertain(state, monkeypatch):
    engine, box_id, inbox_id = state
    fake = FakeImap(count=3)
    fake.capabilities = (b"IMAP4rev1",)
    original_uid = fake.uid
    def fail_store(action, *args):
        if action == "STORE":
            return "NO", [b"refused"]
        return original_uid(action, *args)
    fake.uid = fail_store
    monkeypatch.setattr("ema.mail_folders._connect", lambda box, key: fake)
    with Session(engine) as db:
        box, inbox = db.get(Mailbox, box_id), db.get(MailFolder, inbox_id)
        discover_folders(db, box, "key")
        fetch_folder_page(db, box, "key", inbox)
        message = db.scalar(select(MailMessage).where(MailMessage.uid == 3))
        with pytest.raises(MailError, match="Kopie může být"):
            move_message(db, box, "key", message, "trash")
        assert len(fake.copied) == 1
        assert not fake.uid_expunge
        assert message.moved is False



def test_legacy_trash_larger_than_limit_fails_without_expunge(state, monkeypatch):
    engine, box_id, inbox_id = state
    fake = FakeImap(count=101)
    fake.capabilities = (b"IMAP4rev1",)
    monkeypatch.setattr("ema.mail_folders._connect", lambda box, key: fake)
    with Session(engine) as db:
        box = db.get(Mailbox, box_id)
        discover_folders(db, box, "key")
        trash = special_folder(db, box, "trash")
        with pytest.raises(MailError, match="101 zpráv"):
            empty_trash_batch(db, box, "key", trash, limit=100)
        assert not fake.deleted
        assert fake.full_expunge == 0
        assert not fake.uid_expunge



def test_full_3301_legacy_imap_trash_uses_one_uid_range_and_one_expunge(state, monkeypatch):
    engine, box_id, _ = state
    fake = FakeImap(count=3301)
    fake.capabilities = (b"IMAP4rev1",)
    monkeypatch.setattr("ema.mail_folders._connect", lambda box, key: fake)
    with Session(engine) as db:
        box = db.get(Mailbox, box_id)
        discover_folders(db, box, "key")
        trash = special_folder(db, box, "trash")
        snapshot = preview_trash_all(db, box, "key", trash)
        assert snapshot == {"count": 3301, "uidvalidity": 333, "max_uid": 3301}
        assert not fake.deleted and not fake.full_expunge
        deleted = empty_trash_all(db, box, "key", trash, snapshot)
        assert deleted == 3301
        assert fake.deleted == [("1:3301", "+FLAGS.SILENT", r"(\Deleted)")]
        assert fake.full_expunge == 1
        assert not fake.uid_expunge


def test_full_trash_uidplus_uses_targeted_range(state, monkeypatch):
    engine, box_id, _ = state
    fake = FakeImap(count=260)
    monkeypatch.setattr("ema.mail_folders._connect", lambda box, key: fake)
    with Session(engine) as db:
        box = db.get(Mailbox, box_id)
        discover_folders(db, box, "key")
        trash = special_folder(db, box, "trash")
        snapshot = preview_trash_all(db, box, "key", trash)
        deleted = empty_trash_all(db, box, "key", trash, snapshot)
        assert deleted == 260
        assert fake.deleted == [("1:260", "+FLAGS.SILENT", r"(\Deleted)")]
        assert fake.uid_expunge == ["1:260"]
        assert fake.full_expunge == 0


def test_full_trash_requires_same_server_uid_boundary(state, monkeypatch):
    engine, box_id, _ = state
    fake = FakeImap(count=3301)
    fake.capabilities = (b"IMAP4rev1",)
    monkeypatch.setattr("ema.mail_folders._connect", lambda box, key: fake)
    with Session(engine) as db:
        box = db.get(Mailbox, box_id)
        discover_folders(db, box, "key")
        trash = special_folder(db, box, "trash")
        snapshot = preview_trash_all(db, box, "key", trash)
        fake.count = 3302  # Someone added a new message after user previewed Trash.
        with pytest.raises(MailError, match="Počet nebo UID"):
            empty_trash_all(db, box, "key", trash, snapshot)
        assert fake.deleted == []
        assert fake.full_expunge == 0
        inbox = db.scalar(select(MailFolder).where(
            MailFolder.mailbox_id == box.id, MailFolder.name == "INBOX"))
        with pytest.raises(MailError, match="ověřeným IMAP Košem"):
            empty_trash_all(db, box, "key", inbox, snapshot)
        assert fake.full_expunge == 0
