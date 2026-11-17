"""Idempotent, additive schema upgrade for Ema pilot. Backup DB before running."""
from sqlalchemy import inspect, text
from .models import AssistantTurn, Base


def upgrade_schema(engine):
    """Create assistant turns and add missing legacy mailbox fields, preserving data."""
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        raise RuntimeError("Database is not initialized; run init-db first.")
    # New tables are created separately, never drop or rebuild existing tables.
    Base.metadata.create_all(engine, tables=[AssistantTurn.__table__], checkfirst=True)
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
    inspector = inspect(engine)
    if inspector.has_table("contacts"):
        contact_columns = {col["name"] for col in inspector.get_columns("contacts")}
        if "metadata_json" not in contact_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE contacts ADD COLUMN metadata_json TEXT NULL"))
            applied.append("contacts.metadata_json")
    return applied
