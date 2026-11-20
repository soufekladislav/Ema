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
    # EMA's interface uses Poppins; a received MIME body keeps its own font.
    assert "font-family:Georgia" in preview.srcdoc
    assert "font-family:Poppins" not in preview.srcdoc
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



def test_send_composed_mime_contains_signature_then_original_last(monkeypatch):
    from ema.mail_service import send_composed, encrypt_password
    from cryptography.fernet import Fernet
    saved = []
    class SMTP:
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def login(self,user,password):pass
        def send_message(self,message,to_addrs=None):
            saved.append(message)
    monkeypatch.setattr("ema.mail_service.validate_mail_host",lambda host:host)
    monkeypatch.setattr("ema.mail_service.smtplib.SMTP_SSL",SMTP)
    key=Fernet.generate_key().decode()
    box=SimpleNamespace(smtp_host="smtp.example.cz",smtp_port=465,
                        username="sender@example.cz",smtp_username="",
                        address="sender@example.cz",
                        credential=encrypt_password("sample-password",key))
    raw=send_composed(box,key,"buyer@example.cz","","","Re: Offer",
                      "Děkuji",reply_message_id="<original@example.cz>",
                      signature_html="<strong>EMA podpis</strong>",
                      quoted_original="--- Původní zpráva ---\n> Zpráva")
    assert len(saved)==1
    message=saved[0]
    plain=message.get_body(preferencelist=("plain",)).get_content()
    rich=message.get_body(preferencelist=("html",)).get_content()
    assert plain.index("Děkuji")<plain.index("EMA podpis")<plain.index("Původní zpráva")
    assert rich.index("EMA podpis")<rich.index("Původní zpráva")
    assert message["In-Reply-To"]=="<original@example.cz>"
    assert b"EMA podpis" in raw


def test_signature_save_is_sanitized_and_status_invalidates_when_smtp_changes(seeded,monkeypatch):
    client=seeded
    login(client,"owner")
    box_id=client.ids_v1["box"]
    org=client.application.ids["org"]
    monkeypatch.setattr("ema.web.validate_mail_host",lambda host:host)
    monkeypatch.setattr("ema.web.verify_imap_connection",lambda box,key:(True,"IMAP OK"))
    monkeypatch.setattr("ema.web.verify_smtp_connection",lambda box,key:(True,"SMTP OK"))
    path=f"/org/{org}/mail/{box_id}/edit"
    result=client.post(path,data={
        "csrf_token":csrf(client),"label":"Test mailbox",
        "address":"test@example.cz","username":"test@example.cz",
        "smtp_username":"smtp-test@example.cz",
        "imap_host":"imap.example.cz","smtp_host":"smtp.example.cz",
        "smtp_port":"465","password":"",
        "signature_html":"<b>Podpis</b><script>bad()</script>",
    })
    assert result.status_code==302
    with Session(client.application.extensions["ema_engine"]) as db:
        box=db.get(Mailbox,box_id)
        assert "<b>Podpis</b>" in box.signature_html
        assert "<script" not in box.signature_html
    client.post(f"/org/{org}/mail/{box_id}/check",data={"csrf_token":csrf(client)})
    with Session(client.application.extensions["ema_engine"]) as db:
        assert db.scalar(select(MailboxConnectionCheck).where(
            MailboxConnectionCheck.mailbox_id==box_id)) is not None
    page=client.get(path)
    assert "IMAP OK".encode() in page.data and "SMTP OK".encode() in page.data
    client.post(path,data={
        "csrf_token":csrf(client),"label":"Test mailbox",
        "address":"test@example.cz","username":"test@example.cz",
        "smtp_username":"smtp-test@example.cz",
        "imap_host":"imap.example.cz","smtp_host":"new-smtp.example.cz",
        "smtp_port":"465","password":"",
        "signature_html":"<b>Podpis</b>",
    })
    with Session(client.application.extensions["ema_engine"]) as db:
        assert db.scalar(select(MailboxConnectionCheck).where(
            MailboxConnectionCheck.mailbox_id==box_id)) is None



def test_missing_new_connection_table_does_not_crash_mailbox_settings(seeded,monkeypatch):
    """Code-first deploy: settings remain accessible until the additive migration."""
    client=seeded
    login(client,"owner")
    org=client.application.ids["org"]
    box_id=client.ids_v1["box"]
    engine=client.application.extensions["ema_engine"]
    MailboxConnectionCheck.__table__.drop(engine)
    url=f"/org/{org}/mail/{box_id}/edit"
    page=client.get(url)
    assert page.status_code==200
    assert b"upgrade-db" in page.data
    assert b'Otestovat IMAP + SMTP' not in page.data
    # Never attempt live connections before the status schema is available.
    monkeypatch.setattr("ema.web.verify_imap_connection",
                        lambda *a:pytest.fail("IMAP must not run without schema"))
    response=client.post(f"/org/{org}/mail/{box_id}/check",
                         data={"csrf_token":csrf(client)})
    assert response.status_code==302
    page=client.get(url)
    assert page.status_code==200


def test_reply_over_limit_is_refused_before_smtp_idempotency_row(seeded,monkeypatch):
    """A long original quote may make final message exceed 100k user body limit."""
    from ema.models import Outbound
    client=seeded
    login(client,"owner")
    msg_id=client.ids_v1["message"]
    monkeypatch.setattr("ema.web.original_reply_quote",lambda *args:"Q"*60000)
    send_calls=[]
    monkeypatch.setattr("ema.web.send_composed",lambda *a,**kw:send_calls.append(True))
    nonce="reply-preflight-v13"
    result=client.post("/mail/compose/send",data={
        "csrf_token":csrf(client),"nonce":nonce,
        "box_id":str(client.ids_v1["box"]),"reply_id":str(msg_id),
        "to":"buyer@example.cz","subject":"Re: Offer","body":"B"*50000
    })
    assert result.status_code==422
    assert not send_calls
    with Session(client.application.extensions["ema_engine"]) as db:
        assert db.scalar(select(Outbound.id).where(Outbound.nonce==nonce)) is None



def test_html_only_original_reply_is_converted_to_safe_readable_quote(monkeypatch):
    from ema.mail_compose import original_reply_quote
    original=EmailMessage()
    original.set_content("<html><body><h2>Požadavek</h2>"
                         "<p>Dobrý den,<br>prosím o nabídku.</p>"
                         "<script>steal()</script></body></html>",subtype="html")
    monkeypatch.setattr("ema.mail_compose.fetch_message_mime",
                        lambda *a,**kw:original.as_bytes())
    metadata=SimpleNamespace(sender="Buyer <buyer@example.cz>",
                             recipients="info@example.cz",subject="Nabídka",sent_at=None)
    quoted=original_reply_quote(None,metadata,"key","INBOX")
    assert "Požadavek" in quoted
    assert "Dobrý den," in quoted and "prosím o nabídku." in quoted
    assert "<script>" not in quoted and "steal()" not in quoted
    assert quoted.index("Předmět:") < quoted.index("> Požadavek")
