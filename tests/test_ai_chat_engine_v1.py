"""End-to-end AI Engine console + Boban-like shared private chat integration."""
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from ema.models import AIEngineConnection, AssistantThread, AssistantTurn, AssistantMessageAttempt
from tests.test_navigation import web_client, login, csrf


def test_ai_engine_superadmin_save_encrypt_verify_and_no_secret_in_page(web_client, monkeypatch):
    client = web_client
    app = client.application
    app.config["MAIL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    login(client, "admin")
    token = "connector-key-" + "a" * 64
    page = client.get("/superadmin")
    assert page.status_code == 200
    assert b"ops-intelligence" in page.data
    response = client.post("/superadmin/intelligence/connect",
                           data={"csrf_token": csrf(client), "api_key": token})
    assert response.status_code == 302
    with Session(app.extensions["ema_engine"]) as db:
        conn = db.get(AIEngineConnection, 1)
        assert conn and not conn.verified
        assert token not in conn.encrypted_key
    assert token.encode() not in client.get("/superadmin").data
    assert token.encode() not in client.get("/internal/ops/manifest").data
    recorded = []
    monkeypatch.setattr("ema.web.verify_connector_key",
                        lambda key, base: (recorded.append((key, base)) or True))
    response = client.post("/superadmin/intelligence/verify",
                           data={"csrf_token": csrf(client)})
    assert response.status_code == 302
    assert recorded == [(token, "https://aiengine.freshcrackers.cz")]
    with Session(app.extensions["ema_engine"]) as db:
        saved = db.get(AIEngineConnection, 1)
        assert saved.verified and saved.check_status == "ok" and saved.checked_at


def test_non_admin_cannot_save_engine_credentials(web_client):
    client = web_client
    login(client, "owner")
    result = client.post("/superadmin/intelligence/connect",
                         data={"csrf_token": csrf(client),
                               "api_key": "bad-secret-key-" + "x" * 40})
    assert result.status_code == 403
    with Session(client.application.extensions["ema_engine"]) as db:
        assert db.get(AIEngineConnection, 1) is None


def test_shared_chat_history_is_private_and_nonce_prevents_duplicate_billing(web_client, monkeypatch):
    client = web_client
    app = client.application
    login(client, "owner")
    app.config.update(EMA_AI_ENGINE_API_KEY="legacy-test",
                      EMA_AI_ALLOWED_EMAILS="owner@example.cz")
    seen = []
    def fake_engine(**args):
        seen.append(args)
        return "Ema navrhla další krok, nic neprovedla."
    monkeypatch.setattr("ema.web.run_assistant", fake_engine)
    fresh = client.post("/assistant/threads", data={"csrf_token": csrf(client),
                                                   "project_id": str(app.ids["project"])})
    assert fresh.status_code == 201
    thread_id = fresh.get_json()["id"]
    nonce = "unique-request-0123456789"
    response = client.post("/assistant/api/message", data={
        "csrf_token": csrf(client), "thread_id": str(thread_id),
        "body": "Zkontroluj projekt", "nonce": nonce})
    assert response.status_code == 200
    assert "navrhla další krok" in response.get_json()["answer"]
    assert len(seen) == 1
    again = client.post("/assistant/api/message", data={
        "csrf_token": csrf(client), "thread_id": str(thread_id),
        "body": "Zkontroluj projekt", "nonce": nonce})
    assert again.status_code == 422
    assert len(seen) == 1
    detail = client.get(f"/assistant/threads/{thread_id}")
    assert detail.status_code == 200
    assert len(detail.get_json()["messages"]) == 2
    assert b"Zkontroluj projekt" in client.get(f"/?project={app.ids['project']}&thread={thread_id}").data
    assert b"ema-chat-fab" in client.get("/mail").data
    assert b"ema-chat-fab" in client.get("/tasks").data
    with Session(app.extensions["ema_engine"]) as db:
        attempt = db.scalar(select(AssistantMessageAttempt).where(
            AssistantMessageAttempt.nonce == nonce))
        assert attempt.state == "completed"
        assert db.scalar(select(AssistantThread).where(
            AssistantThread.id == thread_id)).title.startswith("Zkontroluj")
    # Switch identity with an explicit logout: login page does not switch
    # already authenticated users automatically.
    with client.session_transaction() as sess:
        token = sess["csrf"]
    assert client.post("/logout", data={"csrf_token":token}).status_code == 302
    login(client, "guest")
    assert client.get(f"/assistant/threads/{thread_id}").status_code == 404


def test_unverified_saved_connector_never_bills_chat(web_client, monkeypatch):
    client=web_client
    app=client.application
    app.config["MAIL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    login(client,"admin")
    client.post("/superadmin/intelligence/connect",data={
        "csrf_token":csrf(client), "api_key":"connector-" + "a"*64})
    with client.session_transaction() as sess:
        token = sess["csrf"]
    assert client.post("/logout", data={"csrf_token": token}).status_code == 302
    login(client,"owner")
    called=[]
    monkeypatch.setattr("ema.web.run_assistant",lambda **kwargs:called.append(kwargs))
    new=client.post("/assistant/threads",data={"csrf_token":csrf(client)})
    assert new.status_code==201
    response=client.post("/assistant/api/message",data={
        "csrf_token":csrf(client),"thread_id":str(new.get_json()["id"]),
        "body":"Ahoj","nonce":"unverified-attempt-01234"})
    assert response.status_code==422
    assert not called
