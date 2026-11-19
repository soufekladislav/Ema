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
        assert "icons/ema-source.jpg" in html, path
        assert "apple-mobile-web-app-title\" content=\"EMA" in html
        assert "pwa-install-v2.js" in html
        assert "pwa-install-v2.css" in html


def test_pwa_ios_and_android_install_instructions_do_not_fake_installation():
    script = (ROOT / "static" / "pwa-install-v2.js").read_text(encoding="utf-8")
    assert "beforeinstallprompt" in script
    assert "event.preventDefault()" in script
    assert "appinstalled" in script
    assert "deferredPrompt = null" in script
    assert "event.prompt()" in script
    assert "event.userChoice" in script
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
    assert "icons/ema-source.jpg" in area
    assert "Fresh-Crackers-Logo.png" not in area
    assert "<strong>EMA</strong>" in area


def test_pwa_static_assets_and_worker_offline_safety(web_client):
    for file in ("pwa-install-v2.css", "pwa-install-v2.js", "pwa.js"):
        assert web_client.get("/static/" + file).status_code == 200
    worker = web_client.get("/service-worker.js").data.decode("utf-8")
    assert "cache.addAll" in worker
    assert "mail content" in worker
    assert "url.pathname.startsWith" in worker
    assert "/mail" not in worker.split("const SHELL = ", 1)[1].split("];", 1)[0]


def test_pwa_install_diagnostics_and_public_manifest_in_superadmin(web_client):
    client = web_client
    login(client, "admin")
    result = client.get("/superadmin")
    assert result.status_code == 200
    html = result.data.decode("utf-8")
    assert "EMA PWA – instalace a manifest" in html
    assert "Zobrazit manifest" in html
    assert "Otestovat PWA" in html
    assert 'data-ema-pwa-diagnose' in html
    for item in ("ema-pwa-check", "ema-pwa-copy", "ema-pwa-diagnostics-output",
                 "ema-pwa-retry", "Otevřít manifest"):
        assert item in html
    assert client.get("/manifest.webmanifest").status_code == 200


def test_chrome_install_diagnostic_reports_missing_prompt_without_claiming_success():
    script = (ROOT / "static" / "pwa-install-v2.js").read_text(encoding="utf-8")
    assert "beforeinstallprompt" in script
    assert "Chrome zatím nenabídl" in script
    assert "window.isSecureContext" in script
    assert 'credentials:"same-origin",cache:"no-store"' in script
    assert "192x192" in script and "512x512" in script
    assert "getRegistration" in script
    assert "latestReport" in script and "clipboard.writeText" in script
    assert "Zavřít" in (ROOT / "templates" / "base.html").read_text(encoding="utf-8")


def test_manifest_uses_same_origin_installable_icons_not_external_url(web_client):
    data = web_client.get("/manifest.webmanifest").get_json()
    assert all(item["src"].startswith("/static/icons/") for item in data["icons"])
    assert "192x192" in {i["sizes"] for i in data["icons"]}
    assert "512x512" in {i["sizes"] for i in data["icons"]}


def test_chat_uses_original_ema_avatar_not_a_letter(web_client):
    client = web_client
    login(client, "owner")
    page = client.get("/").get_data(as_text=True)
    assert 'class="ema-avatar"><img' in page
    assert 'class="ema-welcome-mark"><img' in page
    assert "icons/ema-avatar.png" in page
    assert "icons/ema-source.jpg" in page
    assert "fresh-hub.png" not in page


def test_updated_pwa_manifest_reuses_install_id_and_busts_icon_cache(web_client):
    manifest = web_client.get("/manifest.webmanifest").get_json()
    assert manifest["id"] == "/mail"
    assert manifest["name"] == "EMA"
    assert manifest["short_name"] == "EMA"
    assert {x["sizes"] for x in manifest["icons"]} == {"192x192", "512x512"}
    assert all("ema-original-20261119" in x["src"] for x in manifest["icons"])
    assert all(x["src"].startswith("/static/icons/ema-") for x in manifest["icons"])
    worker = web_client.get("/service-worker.js").get_data(as_text=True)
    assert "ema-shell-20261119-ai-chat-v1" in worker
    assert "ema-avatar.png" in worker and "ema-source.jpg" in worker
