"""Fresh Engine contract test with no real network requests or credentials."""
import json
from types import SimpleNamespace

import pytest
from ema.assistant_service import AssistantError, run_assistant


def test_engine_contract_uses_only_supplied_project_context(monkeypatch):
    import ema.assistant_service as service

    sent = {}
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def read(self, amount):
            return json.dumps({
                "job_id": "unit-test-id", "status": "completed",
                "output": "Zkontrolovala jsem jeden projekt, bez změn.",
            }).encode("utf-8")

    def fake_urlopen(request, timeout):
        sent["url"] = request.full_url
        sent["authorization"] = request.get_header("Authorization")
        sent["timeout"] = timeout
        sent["payload"] = json.loads(request.data)
        return FakeResponse()

    monkeypatch.setattr(service, "urlopen", fake_urlopen)
    project = SimpleNamespace(id=41, name="Důvěrný projekt", status="active", description="Interní plán")
    task = SimpleNamespace(title="Ověřit nabídku", done=False)
    answer = run_assistant(key="local-test-key", base_url="https://aiengine.freshcrackers.cz",
                           user_id=2, project_id=41, question="Jak pokračovat?",
                           projects=[project], selected_project=project, tasks=[task])
    assert answer == "Zkontrolovala jsem jeden projekt, bez změn."
    assert sent["url"] == "https://aiengine.freshcrackers.cz/v1/engine/run"
    assert sent["authorization"] == "Bearer local-test-key"
    payload = sent["payload"]
    assert payload["source"] == "ema"
    assert payload["operation"] == "assistant.project.chat"
    assert payload["task_type"] == "chat"
    assert payload["max_cost_usd"] == 0.20
    assert payload["project_id"] == "41"
    assert payload["context"]["projects"] == [
        {"id": 41, "name": "Důvěrný projekt", "status": "active", "description": "Interní plán"}
    ]
    assert payload["context"]["selected_project_tasks"][0]["title"] == "Ověřit nabídku"


def test_engine_rejects_insecure_urls_and_missing_key():
    with pytest.raises(AssistantError, match="není připojený"):
        run_assistant(key="", base_url="https://aiengine.freshcrackers.cz",
                      user_id=1, project_id=None, question="Ahoj", projects=[])
    with pytest.raises(AssistantError, match="HTTPS"):
        run_assistant(key="test-key", base_url="http://localhost:5000",
                      user_id=1, project_id=None, question="Ahoj", projects=[])
