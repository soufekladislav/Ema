"""EMA operational diagnostics: read-only, minimal, never expose customer content.

Browser access requires an authenticated *platform* superadmin session.
Automation access uses a distinct read-only SHA256 bearer secret stored outside Git.
An exposed URL by itself never grants access.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets

from sqlalchemy import func, inspect, select, text

from .models import (Base, Audit, AIEngineConnection, Company, Contact, Mailbox,
                     MailboxConnectionCheck, MailMessage, Opportunity,
                     OpsIncident, OpsJobRun, OpsDeployment, Organization, Outbound,
                     Project, Task, User, now)


FINGERPRINT_PATHS = (
    "ema/web.py",
    "ema/models.py",
    "ema/security.py",
    "ema/assistant_service.py",
    "ema/contact_import.py",
    "ema/mail_service.py",
    "ema/mail_folders.py",
    "ema/mail_render.py",
    "ema/mail_compose.py",
    "ema/schema_upgrade.py",
    "ema/ops.py",
    "ema/__init__.py",
    "passenger_wsgi.py",
    "wsgi.py",
    "requirements.txt",
    "templates/app.html",
    "templates/overview.html",
    "templates/base.html",
    "templates/login.html",
    "templates/trash_confirm.html",
    "templates/_mail_rows.html",
    "templates/_mail_quick_preview.html",
    "static/app.css",
    "static/app-v11.css",
    "static/mail-v11.js",
    "static/mail-pager-v11.js",
    "static/mail-actions-v12.js",
    "static/mail-actions-v12.css",
    "static/mail-layout-v13.js",
    "static/mail-layout-v13.css",
    "static/mail-final-v13.css",
    "static/ops-console-v1.css",
    "static/mobile-shell-v2.js",
    "static/mobile-shell-v2.css",
    "static/pwa-install-v2.js",
    "static/pwa-install-v2.css",
    "static/pwa.js",
    "static/sw.js",
    "static/manifest.webmanifest",
)

RELEASE_STEPS = (
    {"release": "Mail V1.2", "github": "PR #81",
     "scope": "MIME, přílohy, IMAP operace, PWA"},
    {"release": "Mail V1.3", "github": "PR #84",
     "scope": "HTML, Trash, pořadí, šířka, odpovědi, podpisy"},
    {"release": "Ops V1", "github": "admin/manifest",
     "scope": "verze, health, worker, incidents, audit, redigovaný manifest"},
)


def _utc(dt):
    return (dt.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
            if dt is not None else None)


def _git_head(root):
    """Read local Git ref without running commands or contacting GitHub."""
    git = root / ".git"
    if not git.is_dir():
        return None
    try:
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if re.fullmatch(r"[0-9a-fA-F]{40,64}", head):
            return head.lower()
        if not head.startswith("ref: "):
            return None
        name = head[5:].strip()
        if not re.fullmatch(r"refs/[A-Za-z0-9/._-]{1,180}", name):
            return None
        file = (git / name).resolve()
        if not file.is_relative_to(git.resolve()):
            return None
        if file.is_file():
            value = file.read_text(encoding="utf-8").strip()
            return value.lower() if re.fullmatch(r"[a-fA-F0-9]{40,64}", value) else None
        packed = git / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8").splitlines():
                parts = line.split(" ")
                if len(parts) == 2 and parts[1] == name and re.fullmatch(r"[a-fA-F0-9]{40,64}", parts[0]):
                    return parts[0].lower()
    except (OSError, UnicodeError, ValueError):
        pass
    return None


def code_identity(root, environment=None):
    environment = environment or os.environ
    raw_sha = (environment.get("EMA_DEPLOY_SHA") or "").strip()
    git_sha = _git_head(root)
    sha, source = (git_sha, "git_checkout") if git_sha else (None, "unknown")
    if sha is None and raw_sha and re.fullmatch(r"[a-fA-F0-9]{40,64}", raw_sha):
        sha, source = raw_sha.lower(), "operator_declared"
    files = {}
    for name in FINGERPRINT_PATHS:
        path = root / name
        try:
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            files[name] = None
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "release": "EMA Ops V1",
        "deployed_commit": sha,
        "commit_source": source,
        "commit_verified_against_github": False,  # Comparisons require GitHub outside EMA.
        "deployed_at": _validated_deploy_time(environment.get("EMA_DEPLOYED_AT", "")),
        "source_fingerprint": hashlib.sha256(canonical).hexdigest(),
        "file_sha256": files,
        "missing_files": [name for name, digest in files.items() if digest is None],
    }


def _validated_deploy_time(value):
    value = str(value or "").strip()
    if not value or len(value) > 40:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat(timespec="seconds")
    except ValueError:
        return None


def _safe_count(db, model, present):
    return (int(db.scalar(select(func.count()).select_from(model)) or 0)
            if model.__tablename__ in present else None)


def _latest(db, model, present, key, limit=12):
    if model.__tablename__ not in present:
        return []
    return db.scalars(select(model).order_by(key.desc()).limit(limit)).all()


def collect_ops(db, root, environment=None):
    """Create one redacted snapshot from the *live* database and deployed files.

    Nothing in this result contains user emails/names, connection strings,
    credentials, messages, arbitrary error texts, audit targets or file content.
    """
    identity = code_identity(root, environment)
    stamp = _utc(now())
    health = {"status": "unknown", "missing_tables": [], "missing_columns": [],
              "migration_required": False}
    stats = {name: None for name in (
        "users", "organizations", "projects", "crm_companies",
        "crm_contacts", "opportunities", "tasks", "mailboxes",
        "indexed_mail_headers", "outbound_attempts",
    )}
    intelligence = {"configured": False, "verified": False, "checked_at": None, "check_status": "not_configured"}
    mailbox = {"total": None, "sync_error": None, "not_synced": None,
               "last_success_at": None, "connection_checked": None,
               "imap_failed": None, "smtp_failed": None}
    jobs, incidents, deployments, audit = [], [], [], {"last_24h_events": None, "recent_actions": []}
    try:
        db.execute(text("SELECT 1"))
        inspector = inspect(db.get_bind())
        present = set(inspector.get_table_names())
        missing = sorted(set(Base.metadata.tables) - present)
        required_columns = {
            "mailboxes": {"smtp_username", "signature_html", "last_sync",
                          "server_message_count"},
            "mail_folders": {"special_use", "delimiter", "uidvalidity"},
            "mail_messages": {"uid", "uidvalidity", "moved"},
        }
        absent = []
        for table, names in required_columns.items():
            if table in present:
                found = {c["name"] for c in inspector.get_columns(table)}
                absent.extend(f"{table}.{name}" for name in sorted(names - found))
        health.update(
            status="ok" if not missing and not absent else "warning",
            missing_tables=missing, missing_columns=absent,
            migration_required=bool(missing or absent),
        )
        for label, model in (
            ("users", User), ("organizations", Organization),
            ("projects", Project), ("crm_companies", Company),
            ("crm_contacts", Contact), ("opportunities", Opportunity),
            ("tasks", Task), ("mailboxes", Mailbox),
            ("indexed_mail_headers", MailMessage), ("outbound_attempts", Outbound),
        ):
            stats[label] = _safe_count(db, model, present)
        if "ai_engine_connections" in present:
            connection = db.get(AIEngineConnection, 1)
            if connection is not None:
                intelligence = {
                    "configured": bool(connection.encrypted_key),
                    "verified": bool(connection.verified),
                    "checked_at": _utc(connection.checked_at),
                    "check_status": connection.check_status,
                }
        if "mailboxes" in present:
            mailbox["total"] = stats["mailboxes"]
            mailbox["sync_error"] = int(db.scalar(select(func.count()).select_from(Mailbox)
                                                 .where(Mailbox.status == "error")) or 0)
            mailbox["not_synced"] = int(db.scalar(select(func.count()).select_from(Mailbox)
                                                 .where(Mailbox.status == "not_synced")) or 0)
            last = db.scalar(select(func.max(Mailbox.last_sync)))
            mailbox["last_success_at"] = _utc(last)
        if "mailbox_connection_checks" in present:
            mailbox["connection_checked"] = _safe_count(db, MailboxConnectionCheck, present)
            mailbox["imap_failed"] = int(db.scalar(select(func.count()).select_from(MailboxConnectionCheck)
                                                  .where(MailboxConnectionCheck.imap_ok.is_(False))) or 0)
            mailbox["smtp_failed"] = int(db.scalar(select(func.count()).select_from(MailboxConnectionCheck)
                                                  .where(MailboxConnectionCheck.smtp_ok.is_(False))) or 0)
        for entry in _latest(db, OpsJobRun, present, OpsJobRun.started_at, 12):
            jobs.append({"name": entry.name, "status": entry.state,
                         "started_at": _utc(entry.started_at),
                         "finished_at": _utc(entry.finished_at),
                         "processed": int(entry.processed or 0),
                         "failed": int(entry.failed or 0)})
        for entry in _latest(db, OpsDeployment, present, OpsDeployment.recorded_at, 12):
            deployments.append({"sha": entry.sha or None, "source": entry.source,
                                "fingerprint": entry.fingerprint,
                                "label": entry.label, "recorded_at": _utc(entry.recorded_at)})
        for entry in _latest(db, OpsIncident, present, OpsIncident.occurred_at, 12):
            incidents.append({"request_id": entry.request_id, "endpoint": entry.endpoint,
                              "category": entry.category, "at": _utc(entry.occurred_at)})
        if "audit_log" in present:
            since = now() - timedelta(hours=24)
            audit["last_24h_events"] = int(db.scalar(select(func.count()).select_from(Audit)
                                                    .where(Audit.created_at >= since)) or 0)
            rows = db.execute(select(Audit.action, func.count(Audit.id))
                              .where(Audit.created_at >= since)
                              .group_by(Audit.action)
                              .order_by(func.count(Audit.id).desc()).limit(12)).all()
            audit["recent_actions"] = [{"action": str(key), "count": int(total)}
                                       for key, total in rows]
    except Exception:
        # Fail closed: do not leak database exception text, SQL statements, URI
        # or credentials into an externally retrievable diagnostics response.
        db.rollback()
        health["status"] = "error"
        health["detail"] = "Diagnostický dotaz do databáze selhal."
    return {
        "schema": "ema.ops.v1",
        "generated_at": stamp,
        "privacy": "metadata_only_no_customer_content",
        "deployed_code": identity,
        "database": health,
        "counts": stats,
        "mail": mailbox,
        "intelligence": intelligence,
        "sync_jobs": jobs,
        "recorded_deployments": deployments,
        "recent_incidents": incidents,
        "audit_summary": audit,
        "release_milestones": list(RELEASE_STEPS),
        "limits": {
            "checks": "passive_only_no_live_imap_calls",
            "background_schedule_verified": False,
            "github_comparison_available": False,
            "exon_deployment_verified": False,
            "server_snapshot_collected": True,
            "incident_history_since_feature_install": True,
        },
    }


def verify_bearer(authorization, expected_sha256):
    """Constant-time service credential, scoped to read-only diagnostic metadata."""
    digest = (expected_sha256 or "").strip().lower()
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        return False
    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        return False
    provided = authorization[7:]
    if not 32 <= len(provided) <= 256 or not re.fullmatch(r"[A-Za-z0-9_.~+-]+", provided):
        return False
    actual = hashlib.sha256(provided.encode("ascii")).hexdigest()
    return secrets.compare_digest(actual, digest)
