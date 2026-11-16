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