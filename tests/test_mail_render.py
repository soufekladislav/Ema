"""MIME rendering must be readable, bounded and never emit executable HTML."""
from email.message import EmailMessage

from ema.mail_render import make_preview, safe_image_url


def test_plain_mime_decodes_quoted_printable_utf8():
    msg = EmailMessage()
    msg["Subject"] = "Česká zpráva"
    msg.set_content("Ahoj, příště pošlu podklady.\nPřeji hezký den.", cte="quoted-printable")
    preview = make_preview(msg.as_bytes())
    assert not preview.is_html
    assert "Ahoj, příště pošlu podklady." in preview.plain
    assert "=C5" not in preview.plain


def test_html_preview_blocks_scripts_forms_images_and_unsafe_links():
    msg = EmailMessage()
    msg.set_content("Obyčejný náhled.")
    msg.add_alternative(
        '<p>Ahoj <strong>kliente</strong>!</p>'
        '<img src="https://tracker.example.org/open?id=1" alt="tracking">'
        '<a href="javascript:alert(1)">Nebezpečný odkaz</a>'
        '<script>alert(1)</script><form action="https://evil.example">ok</form>',
        subtype="html",
    )
    blocked = make_preview(msg.as_bytes())
    assert blocked.is_html
    assert blocked.remote_images
    assert "Ahoj" in blocked.srcdoc
    assert "strong" in blocked.srcdoc
    assert "https://tracker.example.org/open" not in blocked.srcdoc
    assert "<script" not in blocked.srcdoc
    assert "<form" not in blocked.srcdoc
    assert "javascript:alert" not in blocked.srcdoc
    assert "img-src 'none'" in blocked.srcdoc

    enabled = make_preview(msg.as_bytes(), show_images=True)
    assert "https://tracker.example.org/open" in enabled.srcdoc
    assert "img-src https: data:" in enabled.srcdoc
    assert "<script" not in enabled.srcdoc


def test_cid_inline_image_only_after_opt_in():
    msg = EmailMessage()
    msg.set_content("Plain text")
    msg.add_alternative('<p>Logo <img src="cid:logo123" alt="logo"></p>', subtype="html")
    msg.get_payload()[1].add_related(b"\x89PNG\r\n\x1a\n" + b"12345", maintype="image",
                                     subtype="png", cid="<logo123>")
    hidden = make_preview(msg.as_bytes())
    assert "data:image/png" not in hidden.srcdoc
    allowed = make_preview(msg.as_bytes(), show_images=True)
    assert "data:image/png;base64," in allowed.srcdoc


def test_remote_image_hosts_restricted():
    assert safe_image_url("https://cdn.example.cz/img.png")
    assert not safe_image_url("http://cdn.example.cz/img.png")
    assert not safe_image_url("https://127.0.0.1/a.png")
    assert not safe_image_url("https://localhost/a.png")
    assert not safe_image_url("https://user:pass@cdn.example.cz/x.png")
    assert not safe_image_url("javascript:alert(1)")
