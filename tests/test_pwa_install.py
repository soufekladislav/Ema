"""EMA PWA installability, naming, navigation and illustrated launch contracts."""
from pathlib import Path

from tests.test_navigation import web_client, login

ROOT = Path(__file__).resolve().parents[1]


def test_pwa_manifest_named_ema_and_keeps_existing_install_identity(web_client):
    app = web_client.get("/manifest.webmanifest")
    assert app.status_code == 200
    data = app.get_json()
    assert data["name"] == "EMA"
    assert data["short_name"] == "EMA"
    assert data["start_url"] == "/"
    # Changing the id would create a second installed PWA instead of upgrading.
    assert data["id"] == "/mail"
    assert data["scope"] == "/"
    assert data["display"] == "standalone"
    assert {link["url"] for link in data["shortcuts"]} == {"/mail", "/projects", "/tasks"}
    assert {icon["sizes"] for icon in data["icons"]} >= {"192x192", "512x512"}


def test_pwa_install_link_after_account_settings_on_all_primary_pages(web_client):
    client = web_client
    login(client, "owner")
    for path in ("/", "/mail", "/projects", "/database", "/tasks", "/account"):
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.data.decode("utf-8")
        assert 'id="ema-install-button"' in html, path
        assert 'aria-controls="ema-install-dialog"' in html, path
        assert 'id="ema-install-dialog"' in html, path
        assert "Nainstalovat EMA" in html, path
        assert html.index("Nastavení účtu") < html.index("Nainstalovat EMA"), path
        assert 'id="ema-pwa-splash"' in html, path
        assert "2026/10/fresh-hub.png" in html, path
        assert "apple-mobile-web-app-title\" content=\"EMA" in html
        assert "pwa-install-v1.js" in html
        assert "pwa-install-v1.css" in html


def test_pwa_ios_and_android_install_instructions_do_not_fake_installation():
    script = (ROOT / "static" / "pwa-install-v1.js").read_text(encoding="utf-8")
    assert "beforeinstallprompt" in script
    assert "event.preventDefault()" in script
    assert "appinstalled" in script
    assert "pendingInstall = null" in script
    assert "promptEvent.prompt()" in script
    assert "promptEvent.userChoice" in script
    assert 'window.navigator.standalone === true' in script
    assert 'window.matchMedia("(display-mode: standalone)")' in script
    assert "Safari" in script and "Přidat na plochu" in script
    assert "Android" in script and "Chrome" in script
    assert "sessionStorage" in script
    assert "ema.pwa.launch.v1" in script


def test_pwa_start_screen_uses_ema_image_and_no_fresh_crackers_logo(web_client):
    client = web_client
    login(client, "owner")
    html = client.get("/mail").data.decode("utf-8")
    marker = '<div id="ema-pwa-splash"'
    assert marker in html
    area = html.split(marker, 1)[1].split("</div>", 2)[0]
    assert "2026/10/fresh-hub.png" in area
    assert "Fresh-Crackers-Logo.png" not in area
    assert "<strong>EMA</strong>" in area


def test_pwa_static_assets_and_worker_offline_safety(web_client):
    for file in ("pwa-install-v1.css", "pwa-install-v1.js", "pwa.js"):
        assert web_client.get("/static/" + file).status_code == 200
    worker = web_client.get("/service-worker.js").data.decode("utf-8")
    assert "cache.addAll" in worker
    assert "mail content" in worker
    assert "url.pathname.startsWith" in worker
    assert "/mail" not in worker.split("const SHELL = ", 1)[1].split("];", 1)[0]
