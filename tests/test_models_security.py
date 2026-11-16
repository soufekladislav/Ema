import pytest
from sqlalchemy import select
from ema.models import (
    Base, make_session, User, Organization, Membership, Project,
    ProjectGrant, Company, Mailbox, MailboxGrant, ChatMessage,
)
from ema.security import Forbidden, organization_access, project_access, mailbox_access


@pytest.fixture
def db():
    engine, Session = make_session("sqlite://")
    Base.metadata.create_all(engine)
    with Session() as session:
        yield session


def tenants(db):
    alice = User(email="alice@example.com", name="Alice", password_hash="hash")
    bob = User(email="bob@example.com", name="Bob", password_hash="hash")
    other = User(email="other@example.com", name="Other", password_hash="hash", superadmin=True)
    org1, org2 = Organization(name="Firma 1"), Organization(name="Firma 2")
    db.add_all([alice, bob, other, org1, org2])
    db.flush()
    db.add_all([Membership(organization_id=org1.id, user_id=alice.id, role="owner"),
                Membership(organization_id=org2.id, user_id=bob.id, role="owner")])
    project = Project(organization_id=org1.id, name="Projekt Firma 1")
    db.add(project)
    db.commit()
    return alice, bob, other, org1, org2, project


def test_tenant_membership_and_superadmin_privacy(db):
    a, b, superadmin, x, y, p = tenants(db)
    assert organization_access(db, a.id, x.id).role == "owner"
    with pytest.raises(Forbidden):
        organization_access(db, a.id, y.id)
    with pytest.raises(Forbidden):
        organization_access(db, superadmin.id, x.id)


def test_project_only_guest_does_not_inherit_firm_access(db):
    a, b, _, x, y, p = tenants(db)
    db.add(ProjectGrant(project_id=p.id, user_id=b.id, role="viewer"))
    db.commit()
    assert project_access(db, b.id, p.id).id == p.id
    with pytest.raises(Forbidden):
        organization_access(db, b.id, x.id)
    with pytest.raises(Forbidden):
        project_access(db, b.id, p.id, write=True)


def test_mailbox_requires_org_and_explicit_member_grant(db):
    a, b, _, x, y, p = tenants(db)
    box = Mailbox(organization_id=x.id, owner_id=a.id, label="Info", address="info@example.com",
                  username="info", imap_host="imap.example.com", smtp_host="smtp.example.com", credential="cipher")
    db.add(box)
    db.commit()
    assert mailbox_access(db, a.id, box.id).id == box.id
    with pytest.raises(Forbidden):
        mailbox_access(db, b.id, box.id)
    db.add(Membership(organization_id=x.id, user_id=b.id, role="member"))
    db.add(MailboxGrant(mailbox_id=box.id, user_id=b.id, can_send=False))
    db.commit()
    assert mailbox_access(db, b.id, box.id).id == box.id
    with pytest.raises(Forbidden):
        mailbox_access(db, b.id, box.id, send=True)


def test_chat_is_explicitly_scoped(db):
    a, b, _, x, y, p = tenants(db)
    db.add_all([ChatMessage(organization_id=x.id, author_id=a.id, body="Firma"),
                ChatMessage(organization_id=x.id, project_id=p.id, author_id=a.id, body="Projekt"),
                ChatMessage(organization_id=y.id, author_id=b.id, body="Cizí")])
    db.commit()
    company_chat = db.scalars(select(ChatMessage).where(ChatMessage.organization_id == x.id, ChatMessage.project_id.is_(None))).all()
    assert len(company_chat) == 1
    assert company_chat[0].body == "Firma"