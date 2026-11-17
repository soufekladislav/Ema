"""EMA V0.1. Explicitly scoped persistence; SQLite for local tests, MariaDB in production."""
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary,
    Numeric, String, Text, UniqueConstraint, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(190), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    superadmin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Membership(Base):
    __tablename__ = "memberships"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(190), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="planning", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (Index("ix_project_org", "organization_id"),)


class ProjectGrant(Base):
    __tablename__ = "project_grants"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="viewer", nullable=False)
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(190), nullable=False)
    ico: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(190), default="", nullable=False)
    phone: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (Index("ix_company_org", "organization_id"),)


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(190), nullable=False)
    email: Mapped[str] = mapped_column(String(190), default="", nullable=False)
    phone: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    # Source and extra CSV fields are preserved within the same organization boundary.
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (Index("ix_contact_org", "organization_id"),)


class Opportunity(Base):
    __tablename__ = "opportunities"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(190), nullable=False)
    stage: Mapped[str] = mapped_column(String(24), default="lead", nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric(14, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (Index("ix_opp_org", "organization_id"),)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    __table_args__ = (Index("ix_task_org", "organization_id"),)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (Index("ix_chat_scope", "organization_id", "project_id", "id"),)


class AssistantTurn(Base):
    """Personal AI conversation. Kept separate from shared project/team notes."""
    __tablename__ = "assistant_turns"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (Index("ix_assistant_user_project", "user_id", "project_id", "id"),)


class Mailbox(Base):
    __tablename__ = "mailboxes"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str] = mapped_column(String(190), nullable=False)
    username: Mapped[str] = mapped_column(String(190), nullable=False)  # IMAP login
    smtp_username: Mapped[str] = mapped_column(String(190), default="", nullable=False)
    signature_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    imap_host: Mapped[str] = mapped_column(String(190), nullable=False)
    imap_port: Mapped[int] = mapped_column(Integer, default=993)
    smtp_host: Mapped[str] = mapped_column(String(190), nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, default=465)
    credential: Mapped[str] = mapped_column(Text, nullable=False)  # Fernet ciphertext
    status: Mapped[str] = mapped_column(String(24), default="not_synced", nullable=False)
    sync_error: Mapped[str] = mapped_column(String(400), default="", nullable=False)
    last_sync: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (Index("ix_mailbox_org", "organization_id"),)


class MailboxGrant(Base):
    __tablename__ = "mailbox_grants"
    id: Mapped[int] = mapped_column(primary_key=True)
    mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    can_send: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    __table_args__ = (UniqueConstraint("mailbox_id", "user_id"),)


class MailFolder(Base):
    __tablename__ = "mail_folders"
    id: Mapped[int] = mapped_column(primary_key=True)
    mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(190), nullable=False, default="INBOX")
    uidvalidity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_uid: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    __table_args__ = (UniqueConstraint("mailbox_id", "name"),)


class MailMessage(Base):
    __tablename__ = "mail_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=False)
    folder_id: Mapped[int] = mapped_column(ForeignKey("mail_folders.id", ondelete="CASCADE"), nullable=False)
    uidvalidity: Mapped[int] = mapped_column(Integer, nullable=False)
    uid: Mapped[int] = mapped_column(Integer, nullable=False)
    message_id: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    subject: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    sender: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    recipients: Mapped[str] = mapped_column(String(600), default="", nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    flags: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (UniqueConstraint("folder_id", "uidvalidity", "uid"), Index("ix_mail_box_date", "mailbox_id", "id"))


class Outbound(Base):
    __tablename__ = "outbound"
    id: Mapped[int] = mapped_column(primary_key=True)
    nonce: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    recipient: Mapped[str] = mapped_column(String(500), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="sending", nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)


class Audit(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(90), nullable=False)
    target: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


def make_session(database_url):
    engine = create_engine(database_url, pool_pre_ping=True, pool_recycle=1800)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)