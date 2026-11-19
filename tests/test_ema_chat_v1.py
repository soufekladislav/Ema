"""Ema Chat V1: owner-scoped threads, authenticated connector, duplicate cost guard."""
import json
from urllib.error import HTTPError
from types import SimpleNamespace
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

import pytest

from ema.engine_config import encrypt_engine_key, decrypt_engine_key, verify_engine_key, EngineConfigError
from ema.models import AiEngineConnector, AssistantThread, AssistantTurn, AssistantSubmission
from tests.test_navigation import web_client, login, csrf


def test_connector_key_is_encrypted_and_only_superadmin_can_set_or_verify(web_client, monkeypatch):
    app=web_client.application
    app.config["MAIL_ENCRYPTION_KEY"]=Fernet.generate_key().decode()
    key="fresh-ema-connector-"+"a"*35
    login(web_client,"owner")
    assert web_client.post("/superadmin/intelligence/key", data={
        "csrf_token":csrf(web_client), "engine_api_key":key}).status_code == 403
    admin=app.test_client();login(admin,"admin")
    save=admin.post("/superadmin/intelligence/key", data={
        "csrf_token":csrf(admin),"engine_api_key":key})
    assert save.status_code==302
    with Session(app.extensions["ema_engine"]) as db:
        connector=db.get(AiEngineConnector,1)
        assert connector.state=="untested"
        assert key not in connector.secret_ciphertext
        assert decrypt_engine_key(connector.secret_ciphertext,app.config["MAIL_ENCRYPTION_KEY"])==key
    html=admin.get("/superadmin").get_data(as_text=True)
    assert "Inteligence · Fresh AI Engine" in html
    assert key not in html
    assert "Neproběhl" in html
    called=[]
    def fake_probe(provided,base):
        called.append((provided,base))
        return True,200,"verified"
    monkeypatch.setattr("ema.web.verify_engine_key",fake_probe)
    result=admin.post("/superadmin/intelligence/verify",data={"csrf_token":csrf(admin)})
    assert result.status_code==302
    assert called==[(key,"https://aiengine.freshcrackers.cz")]
    with Session(app.extensions["ema_engine"]) as db:
        assert db.get(AiEngineConnector,1).state=="verified"
    assert key not in admin.get("/internal/ops/manifest").get_data(as_text=True)


def test_explicit_verification_bills_one_call_and_checks_key_not_public_health(monkeypatch):
    import ema.engine_config as service
    calls=[]
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):return None
        def read(self,limit):
            return b'{"status":"completed","output":"OK"}'
    def fake_urlopen(req,timeout):
        calls.append(req)
        assert req.full_url=="https://aiengine.freshcrackers.cz/v1/engine/run"
        assert req.get_header("Authorization")=="Bearer K"*0+"Bearer "+"A"*40
        assert json.loads(req.data)["operation"]=="ema.connector.verify"
        return Response()
    monkeypatch.setattr(service,"urlopen",fake_urlopen)
    assert verify_engine_key("A"*40,"https://aiengine.freshcrackers.cz")== (True,200,"verified")
    assert len(calls)==1
    with pytest.raises(EngineConfigError):
        verify_engine_key("A"*40,"http://aiengine.freshcrackers.cz")


def test_401_and_402_return_safe_reason_and_never_leak_server_text(monkeypatch):
    import ema.engine_config as service
    for code,expected in ((401,"invalid_key"),(402,"insufficient_credits")):
        monkeypatch.setattr(service,"urlopen",lambda req,timeout:(_ for _ in ()).throw(
            HTTPError(req.full_url,code,"API_KEY_VISIBLE_IN_ERROR",{},None)))
        ok,http,reason=verify_engine_key("A"*40,"https://aiengine.freshcrackers.cz")
        assert (ok,http,reason)==(False,code,expected)
        assert "API_KEY" not in reason


def test_shared_personal_chat_history_with_context_and_one_billable_attempt(web_client,monkeypatch):
    app=web_client.application
    app.config["MAIL_ENCRYPTION_KEY"]=Fernet.generate_key().decode()
    key="fresh-ema-connector-"+"b"*35
    with Session(app.extensions["ema_engine"]) as db:
        db.add(AiEngineConnector(id=1,secret_ciphertext=encrypt_engine_key(key,app.config["MAIL_ENCRYPTION_KEY"]),
                                 state="verified"))
        db.commit()
    owner=web_client
    login(owner,"owner")
    project=app.ids["project"]
    secret=app.ids["secret_project"]
    assert owner.get("/assistant/threads").json["threads"]==[]
    assert owner.get("/assistant/threads?project_id="+str(secret)).status_code==403
    calls=[]
    def fake_ai(**kwargs):
        calls.append(kwargs)
        return "Doporučuji připravit nabídku."
    monkeypatch.setattr("ema.web.run_assistant",fake_ai)
    nonce="one-unique-user-request-000001"
    post={"csrf_token":csrf(owner),"project_id":str(project),"body":"Jak získat klienta?","nonce":nonce}
    response=owner.post("/assistant",data=post,headers={"Accept":"application/json"})
    assert response.status_code==200
    assert response.json["ok"] is True
    thread=response.json["thread"]["id"]
    assert response.json["answer"]=="Doporučuji připravit nabídku."
    assert len(calls)==1 and calls[0]["key"]==key
    assert calls[0]["project_id"]==project
    details=owner.get(f"/assistant/threads/{thread}").json
    assert [t["role"] for t in details["messages"]]==["user","assistant"]
    assert "Jak získat klienta?" in owner.get("/?project="+str(project)).get_data(as_text=True)
    assert str(thread).encode() in owner.get("/assistant/threads?project_id="+str(project)).data
    # A retry with the same nonce cannot spend money a second time.
    retry=owner.post("/assistant",data={**post,"thread_id":str(thread)},headers={"Accept":"application/json"})
    assert retry.status_code==409 and len(calls)==1
    guest=app.test_client();login(guest,"guest")
    assert guest.get(f"/assistant/threads/{thread}").status_code==404
    assert guest.post(f"/assistant/threads/{thread}/archive",data={"csrf_token":csrf(guest)}).status_code==404
    assert guest.get("/assistant/threads?project_id="+str(project)).json["threads"]==[]
    # Owner archives without deleting saved messages.
    archived=owner.post(f"/assistant/threads/{thread}/archive",data={"csrf_token":csrf(owner)})
    assert archived.status_code==200
    assert owner.get(f"/assistant/threads/{thread}").status_code==404
    with Session(app.extensions["ema_engine"]) as db:
        assert db.get(AssistantThread,thread).archived
        assert len(db.scalars(select(AssistantTurn).where(AssistantTurn.thread_id==thread)).all())==2


def test_old_messages_are_migrated_into_private_thread_without_losing_history(web_client):
    app=web_client.application
    login(web_client,"owner")
    with Session(app.extensions["ema_engine"]) as db:
        db.add(AssistantTurn(user_id=app.ids["owner"],project_id=None,role="user",
                             body="Dřívější zpráva"))
        db.commit()
    data=web_client.get("/assistant/threads").json
    assert len(data["threads"])==1
    assert data["threads"][0]["title"]=="Původní konverzace"
    tid=data["threads"][0]["id"]
    assert "Dřívější zpráva" in str(web_client.get(f"/assistant/threads/{tid}").json)
    assert len(web_client.get("/assistant/threads").json["threads"])==1


def test_chat_requires_verified_db_key_and_does_not_expose_it_in_html(web_client):
    app=web_client.application
    app.config["EMA_AI_ENGINE_API_KEY"]=""
    app.config["MAIL_ENCRYPTION_KEY"]=Fernet.generate_key().decode()
    with Session(app.extensions["ema_engine"]) as db:
        db.add(AiEngineConnector(id=1,secret_ciphertext=encrypt_engine_key(
            "fresh-unverified-key"+"z"*30,app.config["MAIL_ENCRYPTION_KEY"]),state="untested"))
        db.commit()
    login(web_client,"owner")
    assert b"AI zat\xc3\xadm nen\xc3\xad p\xc5\x99ipojena" in web_client.get("/").data
    result=web_client.post("/assistant",data={"csrf_token":csrf(web_client),
                   "body":"Návrh nabídky","nonce":"ui-uncertified-msg-00001"},
                   headers={"Accept":"application/json"})
    assert result.status_code==503
    assert b"fresh-unverified" not in web_client.get("/").data


def test_floating_chat_exists_on_every_major_page_with_shared_routes(web_client):
    login(web_client,"owner")
    for path in ("/","/mail","/projects","/database","/tasks"):
        page=web_client.get(path)
        assert page.status_code==200
        html=page.get_data(as_text=True)
        assert 'data-ema-chat-drawer' in html
        assert 'ema-ai-chat-v1.js' in html
        assert 'ema-ai-chat-v1.css' in html
        assert 'ema-avatar.png' in html



def test_code_first_deploy_is_readable_until_upgrade_db(web_client):
    """A missing new schema cannot turn mail/admin/home into an HTTP 500."""
    app=web_client.application
    engine=app.extensions["ema_engine"]
    AssistantSubmission.__table__.drop(engine)
    AssistantThread.__table__.drop(engine)
    AiEngineConnector.__table__.drop(engine)
    login(web_client,"owner")
    assert web_client.get("/").status_code==200
    assert web_client.get("/mail").status_code==200
    assert web_client.get("/assistant/threads").status_code==503
    request=web_client.post("/assistant",data={
        "csrf_token":csrf(web_client),"body":"Dnes?",
        "nonce":"schema-not-ready-nonce-001"},headers={"Accept":"application/json"})
    assert request.status_code==503
    admin=app.test_client();login(admin,"admin")
    assert admin.get("/superadmin").status_code==200
    assert admin.post("/superadmin/intelligence/key",data={
        "csrf_token":csrf(admin),"engine_api_key":"X"*40}).status_code==302


def test_explicit_disconnect_blocks_old_env_key_after_restart_semantics(web_client, monkeypatch):
    app=web_client.application
    app.config["MAIL_ENCRYPTION_KEY"]=Fernet.generate_key().decode()
    app.config["EMA_AI_ENGINE_API_KEY"]="env-pilot-key"
    app.config["EMA_AI_ALLOWED_EMAILS"]="owner@example.cz"
    admin=app.test_client();login(admin,"admin")
    with Session(app.extensions["ema_engine"]) as db:
        db.add(AiEngineConnector(id=1,secret_ciphertext=encrypt_engine_key(
            "ema-verified-"+"k"*32,app.config["MAIL_ENCRYPTION_KEY"]),state="verified"))
        db.commit()
    result=admin.post("/superadmin/intelligence/disconnect",data={
        "csrf_token":csrf(admin),"confirm":"disconnect"})
    assert result.status_code==302
    with Session(app.extensions["ema_engine"]) as db:
        row=db.get(AiEngineConnector,1)
        assert row.state=="disconnected" and row.secret_ciphertext==""
    login(web_client,"owner")
    outcome=web_client.post("/assistant",data={
        "csrf_token":csrf(web_client),"body":"Dotaz",
        "nonce":"disconnected-guard-0001"},headers={"Accept":"application/json"})
    assert outcome.status_code==503
    with Session(app.extensions["ema_engine"]) as db:
        assert db.scalar(select(AssistantSubmission.id)) is None
