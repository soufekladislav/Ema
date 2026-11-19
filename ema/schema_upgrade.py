"""Idempotent, additive schema upgrade for Ema pilot. Backup DB before running."""
from sqlalchemy import inspect, text, select
from sqlalchemy.orm import Session
from .models import AssistantTurn, AssistantThread, AIEngineConnection, MailboxView, MailUserState, MailboxConnectionCheck, OpsIncident, OpsJobRun, OpsDeployment, Base


def upgrade_schema(engine):
    """Create assistant turns and add missing legacy mailbox fields, preserving data."""
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        raise RuntimeError("Database is not initialized; run init-db first.")
    # New tables are created separately, never drop or rebuild existing tables.
    Base.metadata.create_all(engine, tables=[AssistantTurn.__table__, AssistantThread.__table__, AIEngineConnection.__table__, MailboxView.__table__,
                                                     MailUserState.__table__, MailboxConnectionCheck.__table__,
                                                     OpsIncident.__table__, OpsJobRun.__table__,
                                                     OpsDeployment.__table__], checkfirst=True)
    # Older installations already contain assistant_turns but not thread_id.
    # Add only one nullable reference; no message is deleted or migrated blindly.
    if inspector.has_table("assistant_turns"):
        turns = {c["name"] for c in inspector.get_columns("assistant_turns")}
        if "thread_id" not in turns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE assistant_turns ADD COLUMN thread_id INTEGER NULL"))
    # Preserve pre-V1 conversation: migrate unthreaded turns into one private
    # historic conversation per user/project. Repeatable and non-destructive.
    with Session(engine) as db:
        pairs = db.execute(text(
            "SELECT DISTINCT user_id, project_id FROM assistant_turns WHERE thread_id IS NULL"
        )).all()
        for uid, pid in pairs:
            existing = db.scalar(select(AssistantThread).where(
                AssistantThread.user_id == uid,
                AssistantThread.project_id == pid,
                AssistantThread.title == "Původní konverzace"))
            thread = existing or AssistantThread(user_id=uid, project_id=pid,
                                                 title="Původní konverzace")
            if not existing:
                db.add(thread)
                db.flush()
            rows = db.scalars(select(AssistantTurn).where(
                AssistantTurn.user_id == uid,
                AssistantTurn.project_id == pid,
                AssistantTurn.thread_id.is_(None))).all()
            for row in rows:
                row.thread_id = thread.id
        db.commit()
    inspector = inspect(engine)
    if not inspector.has_table("mailboxes"):
        raise RuntimeError("The mailboxes table is missing.")
    existing = {col["name"] for col in inspector.get_columns("mailboxes")}
    applied = []
    with engine.begin() as conn:
        if "smtp_username" not in existing:
            conn.execute(text("ALTER TABLE mailboxes ADD COLUMN smtp_username VARCHAR(190) NOT NULL DEFAULT ''"))
            applied.append("mailboxes.smtp_username")
        if "signature_html" not in existing:
            # Nullable for portable SQLite/MariaDB TEXT DDL; application always writes a string.
            conn.execute(text("ALTER TABLE mailboxes ADD COLUMN signature_html TEXT"))
            conn.execute(text("UPDATE mailboxes SET signature_html = '' WHERE signature_html IS NULL"))
            applied.append("mailboxes.signature_html")
        if "server_message_count" not in existing:
            conn.execute(text("ALTER TABLE mailboxes ADD COLUMN server_message_count INTEGER NULL"))
            applied.append("mailboxes.server_message_count")
    inspector = inspect(engine)
    if inspector.has_table("mail_folders"):
        columns = {col["name"] for col in inspector.get_columns("mail_folders")}
        with engine.begin() as conn:
            if "special_use" not in columns:
                conn.execute(text("ALTER TABLE mail_folders ADD COLUMN special_use VARCHAR(190) NOT NULL DEFAULT ''"))
                applied.append("mail_folders.special_use")
            if "delimiter" not in columns:
                conn.execute(text("ALTER TABLE mail_folders ADD COLUMN delimiter VARCHAR(10) NOT NULL DEFAULT '/'"))
                applied.append("mail_folders.delimiter")
    inspector = inspect(engine)
    if inspector.has_table("mail_messages"):
        columns = {col["name"] for col in inspector.get_columns("mail_messages")}
        if "moved" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE mail_messages ADD COLUMN moved BOOLEAN NOT NULL DEFAULT 0"))
            applied.append("mail_messages.moved")
    inspector = inspect(engine)
    if inspector.has_table("contacts"):
        contact_columns = {col["name"] for col in inspector.get_columns("contacts")}
        if "metadata_json" not in contact_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE contacts ADD COLUMN metadata_json TEXT NULL"))
            applied.append("contacts.metadata_json")
    inspector = inspect(engine)
    if inspector.has_table("projects"):
        project_columns = {col["name"] for col in inspector.get_columns("projects")}
        if "kind" not in project_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE projects ADD COLUMN kind VARCHAR(20) NOT NULL DEFAULT 'other'"))
            applied.append("projects.kind")
    return applied
