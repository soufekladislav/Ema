"""Ops V1: real metadata, privileged access, strict privacy and graceful failures."""
import hashlib
import re
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from ema.models import Audit, Base, Mailbox, OpsIncident, OpsJobRun, OpsDeployment
from ema.ops import code_identity, collect_ops, verify_bearer
from tests.test_navigation import web_client, login


def test_protected_manifest_requires_superadmin_or_bearer(web_client):
    client = web_client
    assert client.get("/internal/ops/manifest").status_code == 403
    login(client, "owner")
    assert client.get("/superadmin").status_code == 403
    assert client.get("/internal/ops/manifest").status_code == 403
    with client.session_transaction() as sess:
        csrf_token = sess["csrf"]
    assert client.post("/logout", data={"csrf_token":csrf_token}).status_code == 302
    login(client, "admin")
    response = client.get("/internal/ops/manifest")
    assert response.status_code == 200
    assert response.json["schema"] == "ema.ops.v1"
    assert response.json["privacy"] == "metadata_only_no_customer_content"
    assert "no-store" in response.headers["Cache-Control"]
    assert "noindex" in response.headers["X-Robots-Tag"]
    assert "Cookie" in response.headers["Vary"]
    assert client.get("/internal/ops/manifest?download=1").headers[
        "Content-Disposition"].startswith("attachment;")


def test_machine_bearer_is_header_only_and_cannot_open_admin_ui(web_client):
    client = web_client
    token = "karel-readonly-diagnostic-" + ("A" * 48)
    client.application.config["EMA_OPS_MANIFEST_TOKEN_SHA256"] = hashlib.sha256(
        token.encode("ascii")).hexdigest()
    assert client.get("/internal/ops/manifest?token=" + token).status_code == 403
    assert client.get("/internal/ops/manifest", headers={
        "Authorization": "Bearer wrong_secret"}).status_code == 403
    response = client.get("/internal/ops/manifest", headers={
        "Authorization": "Bearer " + token})
    assert response.status_code == 200
    assert "Cache-Control" in response.headers
    assert client.get("/superadmin", headers={
        "Authorization": "Bearer " + token}).status_code == 302
    assert client.post("/superadmin/users", headers={
        "Authorization": "Bearer " + token}).status_code == 400  # CSRF before auth


def test_redacted_manifest_does_not_expose_private_customer_rows(web_client):
    client = web_client
    login(client, "admin")
    report = client.get("/internal/ops/manifest")
    serialized = report.get_data(as_text=True)
    for secret in ("Client secret", "Company-only secret task", "other@example.cz",
                   "owner@example.cz", "secure-password", "SECRET_KEY",
                   "DATABASE_URL", "MAIL_ENCRYPTION_KEY", ".env"):
        assert secret not in serialized
    payload = report.json
    assert payload["counts"]["organizations"] == 2
    assert payload["counts"]["projects"] == 2
    assert payload["database"]["status"] == "ok"
    assert payload["limits"]["github_comparison_available"] is False
    assert payload["deployed_code"]["commit_verified_against_github"] is False


def test_superadmin_console_has_release_schema_jobs_and_errors(web_client):
    client = web_client
    login(client, "admin")
    response = client.get("/superadmin")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for label in ("Administrace Emy", "Verze a nasazení", "Databáze a migrace",
                  "Poštovní konektory", "Fronty a úlohy", "Poslední chyby",
                  "Chráněný manifest", "Správa účtů"):
        if label == "Správa účtů":
            assert "Uživatelé a správa účtů" in html
        else:
            assert label in html
    assert "/internal/ops/manifest" in html
    assert "/static/ops-console-v1.css" in html


def test_service_token_validation_and_source_fingerprint(tmp_path):
    token = "R" * 48
    digest = hashlib.sha256(token.encode()).hexdigest()
    assert verify_bearer("Bearer " + token, digest)
    for header in ("", "Bearer other", "Basic " + token, "Bearer " + token + "?x=1"):
        assert not verify_bearer(header, digest)
    assert not verify_bearer("Bearer " + token, "not configured")
    (tmp_path / "ema").mkdir()
    (tmp_path / "ema" / "web.py").write_text("version 1")
    identity = code_identity(tmp_path, {"EMA_DEPLOY_SHA": "not-a-sha"})
    assert identity["deployed_commit"] is None
    assert identity["commit_source"] == "unknown"
    before = identity["source_fingerprint"]
    (tmp_path / "ema" / "web.py").write_text("version 2")
    after = code_identity(tmp_path)
    assert before != after["source_fingerprint"]
    assert ".env" not in after["file_sha256"]


def test_missing_ops_tables_report_migration_required_without_failing(web_client):
    client = web_client
    engine = client.application.extensions["ema_engine"]
    OpsJobRun.__table__.drop(engine)
    OpsIncident.__table__.drop(engine)
    login(client, "admin")
    manifest = client.get("/internal/ops/manifest")
    assert manifest.status_code == 200
    assert manifest.json["database"]["migration_required"] is True
    assert "ops_incidents" in manifest.json["database"]["missing_tables"]
    assert manifest.json["sync_jobs"] == []
    assert client.get("/superadmin").status_code == 200


def test_worker_cli_writes_real_attempt_not_claimed_cron_schedule(web_client):
    client = web_client
    runner = client.application.test_cli_runner()
    response = runner.invoke(args=["sync-mailboxes", "--limit", "3"])
    assert response.exit_code == 0, response.output
    with Session(client.application.extensions["ema_engine"]) as db:
        last = db.scalar(select(OpsJobRun).order_by(OpsJobRun.id.desc()))
        assert last is not None
        assert last.name == "sync-mailboxes"
        assert last.state == "ok"
        assert last.processed == 0
        assert last.finished_at is not None
    login(client, "admin")
    report = client.get("/internal/ops/manifest").json
    assert report["sync_jobs"][0]["name"] == "sync-mailboxes"
    assert report["limits"]["background_schedule_verified"] is False


def test_unhandled_exception_stores_only_redacted_incident(web_client, monkeypatch):
    client = web_client
    login(client, "admin")
    monkeypatch.setattr("ema.web.collect_ops",
                        lambda *args, **kwargs: (_ for _ in ()).throw(
                            RuntimeError("PASSWORD=never-allow-in-manifest")))
    client.application.config["TESTING"] = False
    client.application.config["PROPAGATE_EXCEPTIONS"] = False
    response = client.get("/superadmin")
    assert response.status_code == 500
    assert "PASSWORD=never-allow-in-manifest" not in response.get_data(as_text=True)
    identifier = re.search(r"ID incidentu: ([0-9a-f]{24})", response.get_data(as_text=True))
    assert identifier
    with Session(client.application.extensions["ema_engine"]) as db:
        item = db.scalar(select(OpsIncident).where(
            OpsIncident.request_id == identifier.group(1)))
        assert item is not None
        assert item.endpoint == "superadmin"
        assert item.category == "unexpected_error"
        assert not hasattr(item, "traceback") and not hasattr(item, "message")



def test_actual_deployment_record_is_explicit_and_deduplicated(web_client):
    client=web_client
    runner=client.application.test_cli_runner()
    first=runner.invoke(args=["ops-record-deploy","--label","main"])
    assert first.exit_code == 0, first.output
    assert "Nasazení zaznamenáno" in first.output
    again=runner.invoke(args=["ops-record-deploy","--label","main"])
    assert again.exit_code == 0
    assert "již je evidován" in again.output
    with Session(client.application.extensions["ema_engine"]) as db:
        records=db.scalars(select(OpsDeployment)).all()
        assert len(records)==1
        assert records[0].fingerprint
    login(client,"admin")
    manifest=client.get("/internal/ops/manifest").json
    assert len(manifest["recorded_deployments"])==1
    assert manifest["recorded_deployments"][0]["fingerprint"] == records[0].fingerprint
    assert "Skutečně zaznamenaná nasazení".encode() in client.get("/superadmin").data


def test_deployment_record_rejects_freeform_sensitive_label(web_client):
    runner=web_client.application.test_cli_runner()
    bad=runner.invoke(args=["ops-record-deploy","--label","secret@example.cz"])
    assert bad.exit_code != 0
    with Session(web_client.application.extensions["ema_engine"]) as db:
        assert db.scalar(select(OpsDeployment.id)) is None
