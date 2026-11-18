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
    assert "img-src data:" in blocked.srcdoc

    enabled = make_preview(msg.as_bytes(), show_images=True)
    assert "https://tracker.example.org/open" in enabled.srcdoc
    assert "img-src https: data:" in enabled.srcdoc
    assert "<script" not in enabled.srcdoc


def test_cid_inline_image_is_local_and_renders_without_remote_tracking():
    msg = EmailMessage()
    msg.set_content("Plain text")
    msg.add_alternative('<p>Logo <img src="cid:logo123" alt="logo"></p>', subtype="html")
    msg.get_payload()[1].add_related(b"\x89PNG\r\n\x1a\n" + b"12345", maintype="image",
                                     subtype="png", cid="<logo123>")
    hidden = make_preview(msg.as_bytes())
    assert "data:image/png" in hidden.srcdoc
    allowed = make_preview(msg.as_bytes(), show_images=True)
    assert "data:image/png;base64," in allowed.srcdoc


def test_remote_image_hosts_restricted():
    assert safe_image_url("https://cdn.example.cz/img.png")
    assert not safe_image_url("http://cdn.example.cz/img.png")
    assert not safe_image_url("https://127.0.0.1/a.png")
    assert not safe_image_url("https://localhost/a.png")
    assert not safe_image_url("https://user:pass@cdn.example.cz/x.png")
    assert not safe_image_url("javascript:alert(1)")

def test_newsletter_css_not_rendered_as_raw_code_and_safe_inline_style_survives():
    msg = EmailMessage()
    msg.set_content("Plain")
    msg.add_alternative(
        '<html><head><style>body { color:red; } table { border: 0; }</style></head>'
        '<body><table><tr><td style="color:green;font-weight:bold">'
        'Zpráva pro zákazníka</td></tr></table>'
        '<script>alert("bad")</script></body></html>',
        subtype="html",
    )
    p = make_preview(msg.as_bytes())
    assert p.is_html
    assert "Zpráva pro zákazníka" in p.srcdoc
    assert "body { color:red" not in p.srcdoc
    assert "table { border: 0" not in p.srcdoc
    assert "alert(" not in p.srcdoc
    assert "color:green" in p.srcdoc or "color: green" in p.srcdoc



def test_newsletter_preserves_safe_css_classes_tables_and_strips_remote_css():
    from email.message import EmailMessage
    from ema.mail_render import make_preview
    msg = EmailMessage()
    msg.set_content("Textová alternativa")
    msg.add_alternative("""
      <html><head>
      <style>
        @import url("https://tracker.example/evil.css");
        @font-face {font-family: X;src:url(https://tracker.example/x.woff)}
        .hero { background-color: #223344; color: #ffffff; padding: 24px; }
        .danger { background-image: url(https://tracker.example/track) }
        table td { padding: 12px; font-size: 18px; }
      </style></head>
      <body><table cellpadding="0" cellspacing="0">
      <tr><td class="hero" style="font-weight:bold">Produktový katalog</td></tr>
      </table><img src="https://tracker.example/pixel" alt="pixel">
      </body></html>
    """, subtype="html")
    preview = make_preview(msg.as_bytes())
    assert preview.is_html
    assert 'class="hero"' in preview.srcdoc
    assert "background-color" in preview.srcdoc
    assert "table td{" in preview.srcdoc
    assert "Produktový katalog" in preview.srcdoc
    assert "tracker.example" not in preview.srcdoc
    assert "@import" not in preview.srcdoc
    assert "@font-face" not in preview.srcdoc
    assert "background-image:" not in preview.srcdoc
    assert "<script" not in preview.srcdoc
    assert "sandbox" not in preview.srcdoc  # sandbox is on the embedding iframe


def test_html_preview_still_works_without_optional_css_parser(monkeypatch):
    import ema.mail_render as renderer
    from email.message import EmailMessage
    msg = EmailMessage()
    msg.set_content("Plain")
    msg.add_alternative(
        '<html><head><style>.title{font-weight:bold}</style></head>'
        '<body><div class="title">Obsah HTML</div></body></html>',
        subtype="html",
    )
    monkeypatch.setattr(renderer, "tinycss2", None)
    preview = renderer.make_preview(msg.as_bytes())
    assert preview.is_html
    assert "Obsah HTML" in preview.srcdoc
    assert "font-weight:bold" not in preview.srcdoc



def test_attachments_index_and_download_are_in_memory_only():
    from ema.mail_render import extract_attachment
    msg = EmailMessage()
    msg.set_content("Přikládám fakturu.")
    msg.add_attachment(b"%PDF-1.7 fake", maintype="application", subtype="pdf",
                       filename="faktura-červen.pdf")
    preview = make_preview(msg.as_bytes())
    assert len(preview.attachments) == 1
    assert preview.attachments[0].filename == "faktura-červen.pdf"
    assert preview.attachments[0].content_type == "application/pdf"
    name, content_type, data = extract_attachment(msg.as_bytes(), 0)
    assert name == "faktura-červen.pdf"
    assert content_type == "application/pdf"
    assert data == b"%PDF-1.7 fake"
    import pytest
    with pytest.raises(IndexError):
        extract_attachment(msg.as_bytes(), 12)


def test_newsletter_keeps_safe_responsive_media_rules_and_poppins_fallback():
    msg = EmailMessage()
    msg.set_content("Text")
    msg.add_alternative("""
    <html><head><style>@media screen and (max-width: 600px) {
      .col {width: 100%; padding: 12px;}
    }</style></head><body><table><tr><td class="col">Nabídka</td></tr></table></body></html>
    """, subtype="html")
    preview = make_preview(msg.as_bytes())
    assert "@media screen and (max-width: 600px)" in preview.srcdoc
    assert "Poppins" in preview.srcdoc
    assert "Nabídka" in preview.srcdoc
