"""EMA V0.1 — Flask application. Server-side authorization for every data path."""
import os
import re
import secrets
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import click
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from .mail_service import MailError, encrypt_password, preview_message, send_plain, sync_inbox, validate_mail_host
from .models import (
    Audit, Base, ChatMessage, Company, Contact, MailFolder, Mailbox, MailboxGrant, MailMessage,
    Membership, Opportunity, Organization, Outbound, Project, ProjectGrant,
    Task, User, make_session, now,
)
from .security import Forbidden, mailbox_access, organization_access, project_access

STAGES = ("lead", "qualified", "proposal", "negotiation", "won", "lost")
PROJ_STATES = ("planning", "active", "paused", "completed")
ORG_ROLES = ("owner", "admin", "member")
PROJECT_ROLES = ("manager", "editor", "viewer")


def field(name, limit=190):
    return (request.form.get(name) or "").strip()[:limit]


def positive_id(name):
    raw = field(name, 20)
    return int(raw) if raw.isdigit() and int(raw) > 0 else None


def required(name, max_len=190):
    value = field(name, max_len)
    if not value:
        abort(400, description=f"Povinné pole: {name}")
    return value


def audit(action, target="", org_id=None):
    g.db.add(Audit(actor_id=g.user.id if g.user else None, organization_id=org_id, action=action[:90], target=str(target)[:150]))


def login_required(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        if not g.user:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return inner


def org_required(fn):
    @wraps(fn)
    @login_required
    def inner(org_id, *args, **kwargs):
        try:
            organization_access(g.db, g.user.id, org_id)
        except Forbidden:
            abort(403)
        g.org = g.db.get(Organization, org_id)
        return fn(org_id, *args, **kwargs)
    return inner


def org_admin(fn):
    @wraps(fn)
    @org_required
    def inner(org_id, *args, **kwargs):
        try:
            organization_access(g.db, g.user.id, org_id, admin=True)
        except Forbidden:
            abort(403)
        return fn(org_id, *args, **kwargs)
    return inner


def admin_required(fn):
    @wraps(fn)
    @login_required
    def inner(*args, **kwargs):
        if not g.user.superadmin:
            abort(403)
        return fn(*args, **kwargs)
    return inner


def project_or_403(project_id, *, write=False, admin=False):
    try:
        return project_access(g.db, g.user.id, project_id, write=write, admin=admin)
    except Forbidden:
        abort(403)


def mailbox_or_403(box_id, *, send=False, manage=False):
    try:
        return mailbox_access(g.db, g.user.id, box_id, send=send, manage=manage)
    except Forbidden:
        abort(403)


def base_context():
    orgs = g.db.scalars(select(Organization).join(Membership).where(Membership.user_id == g.user.id, Organization.active.is_(True)).order_by(Organization.name)).all() if g.user else []
    grants = g.db.scalars(select(Project).join(ProjectGrant).join(Organization, Project.organization_id == Organization.id).where(ProjectGrant.user_id == g.user.id, Organization.active.is_(True)).order_by(Project.name)).all() if g.user else []
    return dict(orgs=orgs, grants=grants, active_org=getattr(g, "org", None), me=g.user)


def render(section, **kwargs):
    context = base_context()
    context.update(section=section, stages=STAGES, project_states=PROJ_STATES, **kwargs)
    return render_template("app.html", **context)


def create_app(test_config=None):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    config = {
        "SECRET_KEY": os.getenv("SECRET_KEY"),
        "DATABASE_URL": os.getenv("DATABASE_URL"),
        "MAIL_ENCRYPTION_KEY": os.getenv("MAIL_ENCRYPTION_KEY", ""),
        "SESSION_COOKIE_SECURE": os.getenv("EMA_HTTPS", "1") != "0",
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=12),
        "MAX_CONTENT_LENGTH": 1024 * 1024,
    }
    if test_config:
        config.update(test_config)
    app.config.update(config)
    if not app.secret_key or not app.config["DATABASE_URL"]:
        raise RuntimeError("Nastavte SECRET_KEY a DATABASE_URL; žádné default produkční heslo není povoleno")
    engine, SessionLocal = make_session(app.config["DATABASE_URL"])
    app.extensions["ema_engine"] = engine

    @app.before_request
    def before():
        g.db = SessionLocal()
        uid = session.get("uid")
        g.user = g.db.get(User, uid) if isinstance(uid, int) else None
        if g.user and not g.user.active:
            session.clear()
            g.user = None
        session.setdefault("csrf", secrets.token_urlsafe(24))
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            if not token or not secrets.compare_digest(str(token), str(session["csrf"])):
                abort(400, description="Neplatný CSRF token")

    @app.teardown_request
    def teardown(error=None):
        if hasattr(g, "db"):
            if error:
                g.db.rollback()
            g.db.close()

    @app.context_processor
    def csrf_context():
        return dict(csrf_token=lambda: session.get("csrf", ""), new_nonce=lambda: secrets.token_urlsafe(24))

    @app.after_request
    def headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
        resp.headers["Cache-Control"] = "no-store" if request.path != "/static" else "public, max-age=3600"
        return resp

    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(400)
    def simple_error(err):
        return (f"{getattr(err, 'code', 400)} — {getattr(err, 'description', 'Chyba požadavku')}", getattr(err, "code", 400), {"Content-Type": "text/plain; charset=utf-8"})

    @app.route("/health")
    def health():
        g.db.execute(text("SELECT 1"))
        return {"service": "ema", "version": "0.1.0", "status": "ok"}

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("home"))
        if request.method == "POST":
            email = field("email").lower()
            user = g.db.scalar(select(User).where(User.email == email))
            if user and user.active and check_password_hash(user.password_hash, request.form.get("password") or ""):
                session.clear()
                session["uid"] = user.id
                session.permanent = True
                return redirect(url_for("home"))
            flash("Přihlášení se nezdařilo", "error")
        return render_template("login.html")

    @app.post("/logout")
    @login_required
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def home():
        return render("home")

    @app.post("/organizations")
    @login_required
    def create_organization():
        name = required("name", 160)
        org = Organization(name=name)
        g.db.add(org)
        g.db.flush()
        g.db.add(Membership(organization_id=org.id, user_id=g.user.id, role="owner"))
        audit("org.create", org.id, org.id)
        g.db.commit()
        return redirect(url_for("organization_home", org_id=org.id))

    @app.route("/org/<int:org_id>")
    @org_required
    def organization_home(org_id):
        counts = {"companies": g.db.scalar(select(func.count(Company.id)).where(Company.organization_id == org_id)),
                  "projects": g.db.scalar(select(func.count(Project.id)).where(Project.organization_id == org_id)),
                  "mailboxes": g.db.scalar(select(func.count(Mailbox.id)).where(Mailbox.organization_id == org_id)),
                  "tasks": g.db.scalar(select(func.count(Task.id)).where(Task.organization_id == org_id, Task.done.is_(False)))}
        return render("org-home", counts=counts)

    @app.route("/org/<int:org_id>/clients")
    @org_required
    def clients(org_id):
        companies = g.db.scalars(select(Company).where(Company.organization_id == org_id).order_by(Company.id.desc()).limit(100)).all()
        contacts = g.db.scalars(select(Contact).where(Contact.organization_id == org_id).order_by(Contact.id.desc()).limit(100)).all()
        return render("clients", companies=companies, contacts=contacts)

    @app.post("/org/<int:org_id>/clients")
    @org_required
    def add_company(org_id):
        obj = Company(organization_id=org_id, name=required("name"), ico=field("ico", 32), email=field("email"), phone=field("phone", 60))
        g.db.add(obj)
        audit("client.create", obj.name, org_id)
        g.db.commit()
        flash("Klient uložen", "success")
        return redirect(url_for("clients", org_id=org_id))

    @app.post("/org/<int:org_id>/contacts")
    @org_required
    def add_contact(org_id):
        company_id = positive_id("company_id")
        if company_id:
            obj = g.db.get(Company, company_id)
            if not obj or obj.organization_id != org_id:
                abort(400, description="Firma kontaktu není ve vašem účtu")
        g.db.add(Contact(organization_id=org_id, company_id=company_id, name=required("name"), email=field("email"), phone=field("phone", 60)))
        audit("contact.create", "", org_id)
        g.db.commit()
        return redirect(url_for("clients", org_id=org_id))

    @app.route("/org/<int:org_id>/pipeline")
    @org_required
    def pipeline(org_id):
        opps = g.db.scalars(select(Opportunity).where(Opportunity.organization_id == org_id).order_by(Opportunity.id.desc()).limit(150)).all()
        companies = g.db.scalars(select(Company).where(Company.organization_id == org_id).order_by(Company.name)).all()
        return render("pipeline", opportunities=opps, companies=companies)

    @app.post("/org/<int:org_id>/pipeline")
    @org_required
    def add_opportunity(org_id):
        company_id = positive_id("company_id")
        if company_id and (not (c := g.db.get(Company, company_id)) or c.organization_id != org_id):
            abort(400)
        opp = Opportunity(organization_id=org_id, company_id=company_id, title=required("title"))
        g.db.add(opp)
        audit("opportunity.create", opp.title, org_id)
        g.db.commit()
        return redirect(url_for("pipeline", org_id=org_id))

    @app.post("/org/<int:org_id>/pipeline/<int:opportunity_id>/stage")
    @org_required
    def change_stage(org_id, opportunity_id):
        opp = g.db.get(Opportunity, opportunity_id)
        if not opp or opp.organization_id != org_id:
            abort(404)
        stage = field("stage", 24)
        if stage not in STAGES:
            abort(400)
        opp.stage = stage
        audit("opportunity.stage", f"{opp.id}:{stage}", org_id)
        g.db.commit()
        return redirect(url_for("pipeline", org_id=org_id))

    @app.route("/org/<int:org_id>/projects")
    @org_required
    def projects(org_id):
        rows = g.db.scalars(select(Project).where(Project.organization_id == org_id).order_by(Project.id.desc()).limit(120)).all()
        return render("projects", projects=rows)

    @app.post("/org/<int:org_id>/projects")
    @org_required
    def add_project(org_id):
        item = Project(organization_id=org_id, name=required("name"), description=field("description", 1500))
        g.db.add(item)
        audit("project.create", item.name, org_id)
        g.db.commit()
        return redirect(url_for("project_detail", project_id=item.id))

    @app.route("/project/<int:project_id>")
    @login_required
    def project_detail(project_id):
        project = project_or_403(project_id)
        rows = g.db.scalars(select(Task).where(Task.project_id == project_id, Task.organization_id == project.organization_id).order_by(Task.id.desc()).limit(80)).all()
        role = g.db.scalar(select(Membership.role).where(Membership.organization_id == project.organization_id, Membership.user_id == g.user.id))
        return render("project", project=project, tasks=rows, can_manage=role in ("owner", "admin"))

    @app.post("/project/<int:project_id>/status")
    @login_required
    def change_project_status(project_id):
        project = project_or_403(project_id, admin=True)
        status = field("status", 30)
        if status not in PROJ_STATES:
            abort(400)
        project.status = status
        audit("project.status", f"{project.id}:{status}", project.organization_id)
        g.db.commit()
        return redirect(url_for("project_detail", project_id=project_id))

    @app.post("/project/<int:project_id>/invite")
    @login_required
    def invite_to_project(project_id):
        project = project_or_403(project_id, admin=True)
        email = required("email").lower()
        role = field("role", 20)
        if role not in PROJECT_ROLES:
            abort(400)
        person = g.db.scalar(select(User).where(User.email == email, User.active.is_(True)))
        if not person:
            flash("Uživatel musí mít nejdříve vytvořený účet", "error")
            return redirect(url_for("project_detail", project_id=project_id))
        grant = g.db.scalar(select(ProjectGrant).where(ProjectGrant.project_id == project_id, ProjectGrant.user_id == person.id))
        if grant:
            grant.role = role
        else:
            g.db.add(ProjectGrant(project_id=project_id, user_id=person.id, role=role))
        audit("project.grant", f"project={project_id}, user={person.id}", project.organization_id)
        g.db.commit()
        flash("Přístup k projektu uložen", "success")
        return redirect(url_for("project_detail", project_id=project_id))

    @app.route("/org/<int:org_id>/tasks")
    @org_required
    def tasks(org_id):
        rows = g.db.scalars(select(Task).where(Task.organization_id == org_id).order_by(Task.done, Task.id.desc()).limit(150)).all()
        projects_list = g.db.scalars(select(Project).where(Project.organization_id == org_id)).all()
        return render("tasks", tasks=rows, projects=projects_list)

    @app.post("/org/<int:org_id>/tasks")
    @org_required
    def add_task(org_id):
        pid = positive_id("project_id")
        if pid and (not (p := g.db.get(Project, pid)) or p.organization_id != org_id):
            abort(400)
        due = field("due", 10)
        try:
            due_at = datetime.strptime(due, "%Y-%m-%d") if due else None
        except ValueError:
            abort(400)
        g.db.add(Task(organization_id=org_id, project_id=pid, title=required("title", 240), due_at=due_at))
        audit("task.create", "", org_id)
        g.db.commit()
        return redirect(url_for("tasks", org_id=org_id))

    @app.post("/org/<int:org_id>/tasks/<int:task_id>/toggle")
    @org_required
    def toggle_task(org_id, task_id):
        row = g.db.get(Task, task_id)
        if not row or row.organization_id != org_id:
            abort(404)
        row.done = not row.done
        audit("task.toggle", row.id, org_id)
        g.db.commit()
        return redirect(url_for("tasks", org_id=org_id))

    @app.route("/org/<int:org_id>/chat", methods=["GET", "POST"])
    @org_required
    def org_chat(org_id):
        if request.method == "POST":
            g.db.add(ChatMessage(organization_id=org_id, author_id=g.user.id, body=required("body", 6000)))
            audit("chat.post", "firm", org_id)
            g.db.commit()
            return redirect(url_for("org_chat", org_id=org_id))
        rows = g.db.scalars(select(ChatMessage).where(ChatMessage.organization_id == org_id, ChatMessage.project_id.is_(None)).order_by(ChatMessage.id.desc()).limit(100)).all()
        return render("chat", chat_messages=list(reversed(rows)), chat_target=url_for("org_chat", org_id=org_id), chat_label="Firemní chat")

    @app.route("/project/<int:project_id>/chat", methods=["GET", "POST"])
    @login_required
    def project_chat(project_id):
        p = project_or_403(project_id, write=request.method == "POST")
        if request.method == "POST":
            g.db.add(ChatMessage(organization_id=p.organization_id, project_id=p.id, author_id=g.user.id, body=required("body", 6000)))
            audit("chat.post", f"project:{p.id}", p.organization_id)
            g.db.commit()
            return redirect(url_for("project_chat", project_id=project_id))
        rows = g.db.scalars(select(ChatMessage).where(ChatMessage.organization_id == p.organization_id, ChatMessage.project_id == p.id).order_by(ChatMessage.id.desc()).limit(100)).all()
        return render("chat", chat_messages=list(reversed(rows)), chat_target=url_for("project_chat", project_id=project_id), chat_label="Projektový chat: " + p.name, project=p)

    @app.route("/org/<int:org_id>/mail")
    @org_required
    def mail(org_id):
        allboxes = g.db.scalars(select(Mailbox).where(Mailbox.organization_id == org_id).order_by(Mailbox.id)).all()
        boxes = []
        for b in allboxes:
            try:
                mailbox_or_403(b.id)
                boxes.append(b)
            except Exception as ex:
                if getattr(ex, "code", None) != 403:
                    raise
        box_id = request.args.get("box", type=int)
        selected = mailbox_or_403(box_id) if box_id else (boxes[0] if boxes else None)
        if selected and selected.organization_id != org_id:
            abort(403)
        rows = g.db.scalars(select(MailMessage).join(MailFolder, MailFolder.id == MailMessage.folder_id).where(MailMessage.mailbox_id == selected.id, MailMessage.uidvalidity == MailFolder.uidvalidity).order_by(MailMessage.id.desc()).limit(100)).all() if selected else []
        return render("mail", boxes=boxes, selected_box=selected, mail_rows=rows)

    @app.post("/org/<int:org_id>/mail/accounts")
    @org_admin
    def add_mailbox(org_id):
        password = request.form.get("password") or ""
        if not password or len(password) > 512:
            abort(400, description="Chybí poštovní heslo/token")
        imap_host, smtp_host = field("imap_host"), field("smtp_host")
        try:
            validate_mail_host(imap_host)
            validate_mail_host(smtp_host)
            encrypted = encrypt_password(password, app.config["MAIL_ENCRYPTION_KEY"])
        except (MailError, ValueError) as ex:
            flash(str(ex), "error")
            return redirect(url_for("settings", org_id=org_id))
        smtp_port = positive_id("smtp_port") or 465
        if smtp_port not in (465, 587):
            abort(400, description="SMTP pouze 465 nebo 587")
        box = Mailbox(organization_id=org_id, owner_id=g.user.id, label=required("label", 120),
                      address=required("address"), username=required("username"), imap_host=imap_host,
                      imap_port=993, smtp_host=smtp_host, smtp_port=smtp_port, credential=encrypted)
        g.db.add(box)
        audit("mailbox.create", box.address, org_id)
        g.db.commit()
        return redirect(url_for("settings", org_id=org_id))

    @app.post("/org/<int:org_id>/mail/<int:box_id>/sync")
    @org_required
    def sync_mail(org_id, box_id):
        box = mailbox_or_403(box_id, manage=True)
        if box.organization_id != org_id:
            abort(403)
        try:
            count = sync_inbox(g.db, box, app.config["MAIL_ENCRYPTION_KEY"], limit=10)
            flash(f"Synchronizováno {count} nových hlaviček; žádné přílohy nebyly uloženy", "success")
        except MailError as ex:
            flash(str(ex), "error")
        return redirect(url_for("mail", org_id=org_id, box=box.id))

    @app.route("/org/<int:org_id>/mail/message/<int:message_id>")
    @org_required
    def mail_detail(org_id, message_id):
        msg = g.db.get(MailMessage, message_id)
        if msg is None:
            abort(404)
        box = mailbox_or_403(msg.mailbox_id)
        if box.organization_id != org_id:
            abort(403)
        try:
            preview = preview_message(box, msg, app.config["MAIL_ENCRYPTION_KEY"])
            warning = "Ukázka je limitovaná na 32 KiB; přílohy se neukládají. HTML/MIME může vyžadovat pozdější parser."
        except MailError as ex:
            preview, warning = "", str(ex)
        companies = g.db.scalars(select(Company).where(Company.organization_id == org_id)).all()
        projs = g.db.scalars(select(Project).where(Project.organization_id == org_id)).all()
        return render("mail-detail", message=msg, selected_box=box, preview=preview, warning=warning, companies=companies, projects=projs)

    @app.post("/org/<int:org_id>/mail/message/<int:message_id>/link")
    @org_required
    def link_mail(org_id, message_id):
        msg = g.db.get(MailMessage, message_id)
        if msg is None:
            abort(404)
        box = mailbox_or_403(msg.mailbox_id)
        if box.organization_id != org_id:
            abort(403)
        cid, pid = positive_id("company_id"), positive_id("project_id")
        if cid and (not (c := g.db.get(Company, cid)) or c.organization_id != org_id):
            abort(400)
        if pid and (not (p := g.db.get(Project, pid)) or p.organization_id != org_id):
            abort(400)
        msg.company_id, msg.project_id = cid, pid
        audit("mail.link", msg.id, org_id)
        g.db.commit()
        return redirect(url_for("mail_detail", org_id=org_id, message_id=message_id))

    @app.post("/org/<int:org_id>/mail/send")
    @org_required
    def mail_send(org_id):
        bid = positive_id("box_id")
        if bid is None:
            abort(400)
        box = mailbox_or_403(bid, send=True)
        if box.organization_id != org_id:
            abort(403)
        nonce = required("nonce", 80)
        if g.db.scalar(select(Outbound.id).where(Outbound.nonce == nonce)):
            flash("Tento pokus o odeslání již byl zpracován; zkontrolujte stav", "error")
            return redirect(url_for("mail", org_id=org_id, box=bid))
        recipient, subject = required("to", 500), required("subject", 500)
        body = required("body", 100000)
        row = Outbound(nonce=nonce, mailbox_id=bid, author_id=g.user.id, recipient=recipient, subject=subject, state="sending")
        g.db.add(row)
        audit("mail.send.request", nonce, org_id)
        g.db.commit()  # Idempotency guard BEFORE sending (avoid blind retries)
        try:
            send_plain(box, app.config["MAIL_ENCRYPTION_KEY"], recipient, subject, body)
            row.state, row.sent_at = "sent", now()
            audit("mail.send.ok", nonce, org_id)
            flash("Zpráva byla předána SMTP serveru", "success")
        except MailError:
            row.state = "uncertain"
            audit("mail.send.uncertain", nonce, org_id)
            flash("Odeslání není potvrzené. Před opakováním zkontrolujte složku Odeslané.", "error")
        g.db.commit()
        return redirect(url_for("mail", org_id=org_id, box=bid))

    @app.route("/org/<int:org_id>/settings")
    @org_required
    def settings(org_id):
        m = organization_access(g.db, g.user.id, org_id)
        is_admin = m.role in ("owner", "admin")
        members = g.db.execute(select(Membership, User).join(User, Membership.user_id == User.id).where(Membership.organization_id == org_id)).all() if is_admin else []
        boxes = g.db.scalars(select(Mailbox).where(Mailbox.organization_id == org_id)).all() if is_admin else []
        return render("settings", membership=m, is_admin=is_admin, members=members, boxes=boxes)

    @app.post("/org/<int:org_id>/members")
    @org_admin
    def add_member(org_id):
        email = required("email").lower()
        role = field("role", 20)
        if role not in ("member", "admin"):
            abort(400)
        user = g.db.scalar(select(User).where(User.email == email, User.active.is_(True)))
        if not user:
            flash("Uživatel nemá účet. Superadmin jej může vytvořit v konzoli.", "error")
            return redirect(url_for("settings", org_id=org_id))
        row = g.db.scalar(select(Membership).where(Membership.organization_id == org_id, Membership.user_id == user.id))
        if row and row.role == "owner":
            abort(400, description="Nelze měnit vlastníka")
        if row:
            row.role = role
        else:
            g.db.add(Membership(organization_id=org_id, user_id=user.id, role=role))
        audit("member.grant", f"user={user.id} role={role}", org_id)
        g.db.commit()
        return redirect(url_for("settings", org_id=org_id))

    @app.route("/superadmin")
    @admin_required
    def superadmin():
        users = g.db.scalars(select(User).order_by(User.id.desc()).limit(100)).all()
        orgs = g.db.scalars(select(Organization).order_by(Organization.id.desc()).limit(100)).all()
        total_messages = g.db.scalar(select(func.count(MailMessage.id)))
        total_mailboxes = g.db.scalar(select(func.count(Mailbox.id)))
        # Shared DB storage cannot be accurately attributed per tenant.
        return render("superadmin", users=users, all_orgs=orgs, total_messages=total_messages,
                      total_mailboxes=total_mailboxes, database_size="Není dostupné bez samostatného měření")

    @app.post("/superadmin/users")
    @admin_required
    def add_user():
        email = required("email").lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            abort(400, description="Neplatná e-mailová adresa")
        password = request.form.get("password") or ""
        if len(password) < 12:
            abort(400, description="Heslo musí mít nejméně 12 znaků")
        g.db.add(User(email=email, name=required("name", 120), password_hash=generate_password_hash(password)))
        audit("user.create", email)
        try:
            g.db.commit()
        except IntegrityError:
            g.db.rollback()
            flash("Účet s tímto e-mailem už existuje", "error")
        return redirect(url_for("superadmin"))

    @app.post("/superadmin/users/<int:user_id>/toggle")
    @admin_required
    def toggle_user(user_id):
        row = g.db.get(User, user_id)
        if row is None or row.id == g.user.id:
            abort(400, description="Vlastní účet nelze pozastavit")
        row.active = not row.active
        audit("user.status", f"id={row.id} active={row.active}")
        g.db.commit()
        return redirect(url_for("superadmin"))

    @app.post("/superadmin/org/<int:org_id>/toggle")
    @admin_required
    def toggle_org(org_id):
        row = g.db.get(Organization, org_id)
        if not row:
            abort(404)
        row.active = not row.active
        audit("org.status", f"id={row.id} active={row.active}")
        g.db.commit()
        return redirect(url_for("superadmin"))

    @app.cli.command("init-db")
    def init_db():
        """Create V0.1 baseline schema; use migrations for future schema changes."""
        Base.metadata.create_all(engine)
        click.echo("EMA V0.1 schema ready")

    @app.cli.command("bootstrap-admin")
    def bootstrap_admin():
        """One-time superadmin, credentials from environment, never CLI args."""
        email = (os.getenv("EMA_BOOTSTRAP_EMAIL") or "").strip().lower()
        password = os.getenv("EMA_BOOTSTRAP_PASSWORD") or ""
        if not email or len(password) < 12:
            raise click.ClickException("Nastavte EMA_BOOTSTRAP_EMAIL a EMA_BOOTSTRAP_PASSWORD (min. 12 znaků)")
        db = SessionLocal()
        try:
            if db.scalar(select(User.id).where(User.email == email)):
                raise click.ClickException("Účet již existuje; neprovádím změnu role ani hesla")
            db.add(User(email=email, name="Superadmin", superadmin=True, password_hash=generate_password_hash(password)))
            db.commit()
            click.echo("Superadmin vytvořen")
        finally:
            db.close()

    @app.cli.command("sync-mailboxes")
    @click.option("--limit", default=20, type=int)
    def sync_mailboxes(limit):
        """Cron-driven bounded mail sync; no long-running web request."""
        db = SessionLocal()
        processed = 0
        try:
            boxes = db.scalars(select(Mailbox).join(Organization).where(Organization.active.is_(True)).order_by(Mailbox.id).limit(50)).all()
            for box in boxes:
                try:
                    processed += sync_inbox(db, box, app.config["MAIL_ENCRYPTION_KEY"], limit=limit)
                    click.echo(f"Mailbox {box.id}: OK")
                except MailError:
                    click.echo(f"Mailbox {box.id}: ERROR (see admin console)")
            click.echo(f"New headers: {processed}")
        finally:
            db.close()

    return app