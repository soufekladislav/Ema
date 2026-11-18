"""EMA Mail V1.3: all six closing requirements without real IMAP deletion."""
from email.message import EmailMessage
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from ema.mail_compose import clean_signature, signature_as_text, outgoing_parts, original_reply_quote
from ema.mail_render import make_preview
from ema.mail_service import MailError, verify_imap_connection, verify_smtp_connection
from ema.models import Mailbox, MailboxConnectionCheck
from tests.test_mail_v1 import seeded
from tests.test_navigation import web_client, login, csrf


def test_safe_html_signature_and_original_reply_always_last():
    clean = clean_signature("<div>Eva <strong>Nováková</strong><script>alert('hack')</script>"
                            "<img src='https://freshcrackers.cz/logo.png' onerror='alert(1)'>"
                            "</div>")
    assert "<script" not in clean and "onerror" not in clean
    assert "Nováková" in signature_as_text(clean)
    text, rich = outgoing_parts("Děkuji za zprávu.", clean, "--- Původní zpráva ---\n> Test")
    assert text.index("Děkuji") < text.index("Nováková") < text.index("Původní zpráva")
    assert rich.index("Nováková") < rich.index("Původní zpráva")
    assert "<script" not in rich


def test_html_only_reply_quotes_original_message_from_imap_without_attachments(monkeypatch):
    mail = EmailMessage()
    mail.set_content("fallback")
    mail.add_alternative("<html><body><div>Dobrý den,<br>poptávka.</div>"
                         "<script>bad</script></body></html>", subtype="html")
    mail.add_attachment(b"%PDF", maintype="application", subtype="pdf",
                        filename="quote-should-not-attach.pdf")
    monkeypatch.setattr("ema.mail_compose.fetch_message_mime",
                        lambda *args, **kwargs: mail.as_bytes())
    source = SimpleNamespace(sender="Customer <c@example.cz>", recipients="info@example.cz",
                             subject="Poptávka", sent_at=None)
    quote = original_reply_quote(None, source, "key", "INBOX")
    assert "> fallback" in quote
    assert "quote-should-not-attach" not in quote
    assert quote.endswith("> fallback")


def test_exact_newsletter_dimensions_keep_sender_layout_and_block_scripts():
    msg = EmailMessage()
    msg.set_content("Text")
    msg.add_alternative(
        "<html><head><style>.hero{font-size:22px;padding:14px}</style></head>"
        "<body style='font-family:Georgia;background-color:#ffffff'>"
        "<table width='620' cellspacing='0'><tr><td width='80%' class='hero' "
        "style='padding:14px'>Vítejte</td></tr></table><script>alert(1)</script>"
        "</body></html>", subtype="html")
    preview = make_preview(msg.as_bytes())
    assert 'width="620"' in preview.srcdoc
    assert 'width="80%"' in preview.srcdoc
    assert "font-family:Georgia" in preview.srcdoc
    assert "Poppins" in preview.srcdoc
    assert "alert(1)" not in preview.srcdoc
    assert "td,th{padding:4px}" not in preview.srcdoc


def test_mail_layout_has_resize_and_persisted_order(seeded):
    client = seeded
    login(client, "owner")
    html = client.get("/mail").data.decode("utf-8")
    assert 'id="ema-mail-pane-resizer"' in html
    assert 'data-user-id=' in html
    assert "/static/mail-layout-v13.js" in html
    assert "/static/mail-layout-v13.css" in html
    js = client.get("/static/mail-layout-v13.js").data.decode("utf-8")
    assert "localStorage.setItem" in js
    assert "queued = true" in js and "if (sending) return;" in js
    assert "role=\"separator\"" in html


def test_mailbox_connection_is_explicit_persistent_and_sends_nothing(seeded, monkeypatch):
    client = seeded
    login(client, "owner")
    box_id = client.ids_v1["box"]
    org_id = client.application.ids["org"]
    monkeypatch.setattr("ema.web.verify_imap_connection",
                        lambda box,key: (True,"IMAP přihlášení ověřeno"))
    monkeypatch.setattr("ema.web.verify_smtp_connection",
                        lambda box,key: (False,"SMTP odmítl test"))
    result = client.post(f"/org/{org_id}/mail/{box_id}/check",
                         data={"csrf_token":csrf(client)})
    assert result.status_code == 302
    with Session(client.application.extensions["ema_engine"]) as db:
        row = db.scalar(select(MailboxConnectionCheck).where(
            MailboxConnectionCheck.mailbox_id == box_id))
        assert row.imap_ok and not row.smtp_ok
    page = client.get(f"/org/{org_id}/mail/{box_id}/edit")
    assert page.status_code == 200
    assert "IMAP přihlášení ověřeno".encode() in page.data
    assert "SMTP odmítl test".encode() in page.data
    guest = client.application.test_client()
    login(guest,"guest")
    assert guest.post(f"/org/{org_id}/mail/{box_id}/check",
                      data={"csrf_token":csrf(guest)}).status_code == 403


def test_smtp_noop_check_does_not_call_send_message(monkeypatch):
    calls = []
    class Dummy:
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def login(self, user,password):calls.append("login")
        def noop(self):calls.append("noop");return 250,b"OK"
        def send_message(self,*args):raise AssertionError("Test must never send")
    box=SimpleNamespace(smtp_host="smtp.example.cz",smtp_port=465,
                        smtp_username="somebody@example.cz",username="somebody@example.cz",
                        credential="dummy")
    monkeypatch.setattr("ema.mail_service.validate_mail_host",lambda host:host)
    monkeypatch.setattr("ema.mail_service.decrypt_password",lambda cred,key:"pw")
    monkeypatch.setattr("ema.mail_service.smtplib.SMTP_SSL",Dummy)
    ok, message=verify_smtp_connection(box,"key")
    assert ok and calls == ["login","noop"]
    assert "bez odeslání" in message


def test_imap_check_readonly(monkeypatch):
    calls=[]
    class Dummy:
        def select(self,folder,readonly=False):
            calls.append((folder,readonly));return "OK",[b"1"]
        def logout(self):calls.append("logout")
    monkeypatch.setattr("ema.mail_service._connect",lambda box,key:Dummy())
    ok,_=verify_imap_connection(None,"key")
    assert ok
    assert calls == [("INBOX",True),"logout"]
