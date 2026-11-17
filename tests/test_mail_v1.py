"""P0 acceptance tests: safe one-click mail client, composer, mobile/PWA and ACL."""
from email.message import EmailMessage

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from ema.mail_render import MailPreview, make_preview
from ema.models import Contact, Mailbox, MailFolder, MailMessage, MailUserState, Outbound
from tests.test_navigation import web_client, login, csrf


@pytest.fixture
def seeded(web_client):
    client = web_client
    ids = client.application.ids
    with Session(client.application.extensions["ema_engine"]) as db:
        box = Mailbox(organization_id=ids["org"], owner_id=ids["owner"],
                      label="Test mailbox", address="test@example.cz", username="test@example.cz",
                      smtp_username="smtp-test@example.cz", imap_host="imap.example.cz",
                      smtp_host="smtp.example.cz", smtp_port=465, credential="test-only")
        other = Mailbox(organization_id=ids["secret_org"], owner_id=ids["owner"],
                        label="Secret", address="secret@example.cz", username="secret@example.cz",
                        imap_host="imap.example.cz", smtp_host="smtp.example.cz", credential="test-only")
        db.add_all([box, other])
        db.flush()
        f = MailFolder(mailbox_id=box.id, name="INBOX", uidvalidity=9)
        f2 = MailFolder(mailbox_id=other.id, name="INBOX", uidvalidity=9)
        db.add_all([f, f2])
        db.flush()
        m = MailMessage(mailbox_id=box.id, folder_id=f.id, uidvalidity=9, uid=11,
                        subject="Please send offer", sender="Buyer <buyer@example.cz>",
                        recipients="test@example.cz", message_id="<buyer-mail@example.cz>", flags="")
        m2 = MailMessage(mailbox_id=other.id, folder_id=f2.id, uidvalidity=9, uid=12,
                         subject="Private", sender="private@example.cz")
        db.add_all([m,m2,
            Contact(organization_id=ids["org"], name="Buyer", email="buyer@example.cz"),
            Contact(organization_id=ids["secret_org"], name="Secret contact", email="secret-contact@example.cz"),
        ])
        db.commit()
        client.ids_v1 = {"box":box.id,"other":other.id,"message":m.id,"private":m2.id}
    return client


def test_compact_inbox_and_inline_mime_preview(seeded, monkeypatch):
    client=seeded
    login(client,"owner")
    html=client.get(f"/mail?box={client.ids_v1['box']}").data
    assert b"ema-mail-v1-topbar" in html
    assert b"ema-mail-folder-tree" in html
    assert b"ema-mail-scrollpanel" in html
    assert b"ema-mail-quick-link" in html
    assert "Napsat e-mail".encode() in html
    assert b"ema-select-all" in html
    assert b"ema-mobile-nav-toggle" in html
    def fake_preview(*args, **kwargs):
        return MailPreview("<p>Safe HTML</p>","Safe plain",True,False,False)
    monkeypatch.setattr("ema.web.preview_message",fake_preview)
    quick=client.get(f"/mail/{client.ids_v1['message']}/quick")
    assert quick.status_code==200
    assert b"Safe HTML" in quick.json["html"].encode()
    assert b"Odpov" in quick.json["html"].encode()
    with Session(client.application.extensions["ema_engine"]) as db:
        state=db.scalar(select(MailUserState).where(
            MailUserState.mail_id==client.ids_v1["message"]))
        assert state.read_override is True
    guest=client.application.test_client()
    login(guest,"guest")
    assert guest.get(f"/mail/{client.ids_v1['message']}/quick").status_code==403


def test_compose_reply_uses_exact_sender_and_company_contacts(seeded,monkeypatch):
    client=seeded
    login(client,"owner")
    b=client.ids_v1["box"]
    mid=client.ids_v1["message"]
    response=client.get(f"/mail/compose?reply_id={mid}")
    assert response.status_code==200
    assert b"buyer@example.cz" in response.data
    assert b"Re: Please send offer" in response.data
    suggest=client.get(f"/mail/contacts/suggest?box={b}&q=buyer")
    assert suggest.status_code==200
    assert [x["email"] for x in suggest.json["contacts"]] == ["buyer@example.cz"]
    assert client.get(f"/mail/contacts/suggest?box={client.ids_v1['other']}&q=secret").status_code==403
    called=[]
    def fake_send(box,key,to,cc,bcc,subject,body,*,reply_message_id=None,attachments=None):
        called.append((box.id,to,cc,bcc,subject,body,reply_message_id,attachments))
    monkeypatch.setattr("ema.web.send_composed",fake_send)
    form={"csrf_token":csrf(client),"nonce":"unique-v1-send",
          "box_id":str(b),"reply_id":str(mid),"to":"buyer@example.cz",
          "cc":"coworker@example.cz","bcc":"","subject":"Re: Please send offer",
          "body":"Sending the offer."}
    res=client.post("/mail/compose/send",data=form)
    assert res.status_code==302
    assert len(called)==1
    assert called[0][0]==b
    assert called[0][6]=="<buyer-mail@example.cz>"
    with Session(client.application.extensions["ema_engine"]) as db:
        row=db.scalar(select(Outbound).where(Outbound.nonce=="unique-v1-send"))
        assert row.state=="sent"
    repeat=client.post("/mail/compose/send",data=form)
    assert repeat.status_code==302 and len(called)==1
    guest=client.application.test_client()
    login(guest,"guest")
    assert guest.get(f"/mail/compose?reply_id={mid}").status_code==403
    assert guest.post("/mail/compose/send",data=form).status_code==400  # alien csrf token


def test_one_click_trash_and_bulk_acl(seeded,monkeypatch):
    client=seeded
    login(client,"owner")
    msg=client.ids_v1["message"]
    target=MailFolder(id=1234,name="Trash",mailbox_id=client.ids_v1["box"],uidvalidity=9)
    called=[]
    def fake_move(db,box,key,message,action):
        called.append(action)
        message.moved=True
        db.commit()
        return target
    monkeypatch.setattr("ema.web.move_message",fake_move)
    try_alien=client.post("/mail/bulk",data={
        "csrf_token":csrf(client),"action":"trash",
        "mail_ids":[str(msg),str(client.ids_v1["private"])]})
    assert try_alien.status_code==403
    assert called==[]
    res=client.post(f"/mail/{msg}/quick-move",data={
        "csrf_token":csrf(client),"action":"trash"})
    assert res.status_code==302
    assert called==["trash"]
    with Session(client.application.extensions["ema_engine"]) as db:
        assert db.get(MailMessage,msg).moved is True


def test_pwa_shell_and_private_http_cache_policy(seeded):
    client=seeded
    manifest=client.get("/manifest.webmanifest")
    assert manifest.status_code==200
    assert manifest.json["display"]=="standalone"
    assert any("512" in x["sizes"] for x in manifest.json["icons"])
    assert client.get("/static/icons/ema-192.png").data[:8]==b"\x89PNG\r\n\x1a\n"
    assert client.get("/static/icons/ema-512.png").data[:8]==b"\x89PNG\r\n\x1a\n"
    worker=client.get("/service-worker.js")
    assert worker.status_code==200
    assert b"caches.open" in worker.data
    assert b'ALLOWED.has(url.pathname)' in worker.data
    assert b'req.mode === "navigate"' in worker.data
    assert b"mail content" in worker.data
    login(client,"owner")
    mailbox=client.get("/mail")
    assert mailbox.headers["Cache-Control"]=="no-store"
    assert b"manifest.webmanifest" in mailbox.data
