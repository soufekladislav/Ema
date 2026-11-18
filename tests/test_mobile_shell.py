"""Shared mobile navigation contract across all authenticated EMA pages.

These tests check rendered server templates and CSS/JS wiring. They do not
substitute for device/browser-based visual acceptance at 320–760 px.
"""
from pathlib import Path

from tests.test_navigation import web_client, login

ROOT = Path(__file__).resolve().parents[1]


def test_mobile_drawer_and_ema_artwork_on_all_primary_pages(web_client):
    client = web_client
    login(client, "owner")
    for path in ("/", "/mail", "/projects", "/database", "/tasks", "/account"):
        result = client.get(path)
        assert result.status_code == 200, path
        body = result.data.decode("utf-8")
        assert 'id="ema-mobile-nav-toggle"' in body, path
        assert 'aria-controls="ema-app-main-nav"' in body, path
        assert 'id="ema-app-main-nav"' in body, path
        assert 'id="ema-appmenu-close"' in body, path
        assert 'id="ema-appmenu-backdrop"' in body, path
        assert "2026/10/fresh-hub.png" in body, path
        assert "Chat / Nástěnka" in body, path
        assert "Databáze / CRM" in body, path


def test_mobile_drawer_on_superadmin_page(web_client):
    client = web_client
    login(client, "admin")
    response = client.get("/superadmin")
    assert response.status_code == 200
    assert b'ema-app-main-nav' in response.data
    assert b'ema-mobile-nav-toggle' in response.data


def test_mobile_shell_css_js_have_closed_state_and_accessible_dismissal():
    css = (ROOT / "static" / "mobile-shell-v2.css").read_text(encoding="utf-8")
    script = (ROOT / "static" / "mobile-shell-v2.js").read_text(encoding="utf-8")
    worker = (ROOT / "static" / "sw.js").read_text(encoding="utf-8")
    assert "body.ema-appmenu-open .layout > aside.sidebar {display:flex!important}" in css
    assert "body .layout > aside.sidebar" in css
    assert "sidebar-hero img" in css
    assert "#ema-appmenu-backdrop:not([hidden])" in css
    assert "function close(" in script and 'ev.key === "Escape"' in script
    assert "stopImmediatePropagation()" in script  # bypass cache-first old handler
    assert 'window.matchMedia("(max-width:760px)")' in script
    assert "sidebar.querySelectorAll" in script
    assert "/static/app.css" not in worker
    assert "/static/mail-v1.js" not in worker
    assert "url.pathname.startsWith(\"/static/\")" in worker


def test_mobile_shell_is_shared_by_secondary_company_and_project_pages(web_client):
    client = web_client
    login(client, "owner")
    org = client.application.ids["org"]
    project = client.application.ids["project"]
    paths = (
        f"/org/{org}", f"/org/{org}/clients", f"/org/{org}/pipeline",
        f"/org/{org}/projects", f"/org/{org}/tasks", f"/org/{org}/chat",
        f"/org/{org}/mail", f"/org/{org}/settings",
        f"/project/{project}", f"/project/{project}/chat",
        "/mail/compose",
    )
    for path in paths:
        result = client.get(path)
        assert result.status_code == 200, (path, result.status_code)
        assert b'id="ema-app-main-nav"' in result.data, path
        assert b'id="ema-mobile-nav-toggle"' in result.data, path
        assert b'id="ema-appmenu-backdrop"' in result.data, path
        assert b"2026/10/fresh-hub.png" in result.data, path



def test_release_assets_bypass_stale_cache_first_pwa(web_client):
    client = web_client
    login(client, "owner")
    html = client.get("/mail").data.decode("utf-8")
    for asset in ("app-v11.css", "mail-v11.js", "mail-pager-v11.js",
                  "mobile-shell-v2.css", "mobile-shell-v2.js"):
        assert "/static/" + asset in html
        response = client.get("/static/" + asset)
        assert response.status_code == 200
    sw = client.get("/service-worker.js").data.decode("utf-8")
    assert "cache.addAll" in sw
    assert '"/static/app.css"' not in sw
    assert '"/static/mail-v1.js"' not in sw
