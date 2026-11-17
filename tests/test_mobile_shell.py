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
    css = (ROOT / "static" / "app.css").read_text(encoding="utf-8")
    script = (ROOT / "static" / "mail-v1.js").read_text(encoding="utf-8")
    assert "body.ema-appmenu-open .layout > .sidebar," in css
    assert "body.ema-screen-mail.ema-appmenu-open .layout > .sidebar{display:flex}" in css
    assert ".sidebar .sidebar-hero img{display:block" in css
    assert ".ema-appmenu-backdrop:not([hidden])" in css
    assert "closeAppMenu" in script and 'event.key === "Escape"' in script
    assert "window.innerWidth > 760" in script
    assert "appSidebar.querySelectorAll" in script
