"""Server-side access rules. Platform superadmin is NOT a customer data superuser."""
from sqlalchemy import select
from .models import Membership, Project, ProjectGrant, Mailbox, MailboxGrant, Organization


class Forbidden(Exception):
    pass


def membership(db, uid, oid):
    org = db.get(Organization, oid)
    if org is None or not org.active:
        raise Forbidden("Firma není dostupná")
    m = db.scalar(select(Membership).where(Membership.user_id == uid, Membership.organization_id == oid))
    if not m:
        raise Forbidden("Nemáte oprávnění k této firmě")
    return m


def organization_access(db, uid, oid, write=False, admin=False):
    m = membership(db, uid, oid)
    if admin and m.role not in ("owner", "admin"):
        raise Forbidden("Správa firmy je vyhrazena administrátorům")
    if write and m.role not in ("owner", "admin", "member"):
        raise Forbidden("Nedostatečné oprávnění")
    return m


def project_access(db, uid, project_id, write=False, admin=False):
    p = db.get(Project, project_id)
    if p is None:
        raise Forbidden("Projekt nenalezen")
    org = db.get(Organization, p.organization_id)
    if org is None or not org.active:
        raise Forbidden("Firma není aktivní")
    m = db.scalar(select(Membership).where(Membership.user_id == uid, Membership.organization_id == p.organization_id))
    grant = db.scalar(select(ProjectGrant).where(ProjectGrant.project_id == project_id, ProjectGrant.user_id == uid))
    if m and m.role in ("owner", "admin"):
        return p
    if admin:
        raise Forbidden("Projekt spravuje vlastník nebo administrátor firmy")
    if m and m.role == "member" and not write:
        return p
    if grant and (not write or grant.role in ("manager", "editor")):
        return p
    # Company members can work with all commercial projects; project-only users only with assigned projects.
    if m and m.role == "member" and write:
        return p
    raise Forbidden("Nemáte oprávnění k projektu")


def mailbox_access(db, uid, mailbox_id, *, send=False, manage=False):
    box = db.get(Mailbox, mailbox_id)
    if box is None:
        raise Forbidden("Schránka nenalezena")
    m = db.scalar(select(Membership).where(Membership.user_id == uid, Membership.organization_id == box.organization_id))
    if m is None:
        raise Forbidden("Schránka nenáleží k přístupné firmě")
    if m.role in ("owner", "admin") or box.owner_id == uid:
        return box
    if manage:
        raise Forbidden("Nelze spravovat cizí schránku")
    grant = db.scalar(select(MailboxGrant).where(MailboxGrant.mailbox_id == mailbox_id, MailboxGrant.user_id == uid))
    if grant and (not send or grant.can_send):
        return box
    raise Forbidden("Nemáte přístup ke schránce")