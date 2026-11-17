"""Read-only MIME/HTML rendering. Never persists message bodies or images."""
import base64
import html
import ipaddress
import re
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from urllib.parse import urlsplit

import bleach
from bleach.css_sanitizer import CSSSanitizer


MAX_PREVIEW_BYTES = 196608
ALLOWED_TAGS = {
    "a", "b", "blockquote", "br", "caption", "center", "code", "dd", "del",
    "div", "dl", "dt", "em", "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "i", "img", "li", "ol", "p", "pre", "s", "small", "span",
    "strong", "sub", "sup", "table", "tbody", "td", "th", "thead",
    "tr", "u", "ul",
}
IMAGE_MIME = {"image/png", "image/jpeg", "image/gif", "image/webp"}
EMAIL_CSS = CSSSanitizer(allowed_css_properties={
    "color", "background", "background-color", "font", "font-size", "font-weight", "font-family",
    "font-style", "text-align", "text-decoration", "line-height", "letter-spacing",
    "margin", "margin-top", "margin-bottom", "margin-left", "margin-right", "padding",
    "padding-top", "padding-bottom", "padding-left", "padding-right", "border",
    "border-color", "border-style", "border-width", "border-collapse", "border-radius",
    "width", "max-width", "min-width", "height", "max-height", "vertical-align",
    "display", "white-space", "word-break", "overflow-wrap",
})



@dataclass
class MailPreview:
    srcdoc: str
    plain: str
    is_html: bool
    remote_images: bool
    truncated: bool


def safe_image_url(value):
    """Only public https hostnames; never fetch on the server."""
    if not value or len(value) > 2048:
        return False
    try:
        url = urlsplit(value)
        hostname = (url.hostname or "").lower()
        if url.scheme.lower() != "https" or not hostname or not hostname.count("."):
            return False
        if url.username or url.password or hostname.endswith((".local", ".internal", ".localhost")):
            return False
        try:
            ipaddress.ip_address(hostname)
            return False
        except ValueError:
            return True
    except ValueError:
        return False


def make_preview(data, *, show_images=False, truncated=False):
    """Parse a capped raw RFC822 MIME slice; untrusted HTML is bleached and sandboxed."""
    msg = BytesParser(policy=policy.default).parsebytes(data or b"")
    plain, rich = "", ""
    cid_images = {}
    for part in msg.walk():
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type()
        if content_type in ("text/plain", "text/html"):
            try:
                body = part.get_content()
                if not isinstance(body, str):
                    body = body.decode(part.get_content_charset() or "utf-8", "replace")
            except (LookupError, UnicodeError, ValueError, TypeError):
                payload = part.get_payload(decode=True) or b""
                body = payload.decode("utf-8", "replace")
            if content_type == "text/html" and not rich:
                rich = body[:MAX_PREVIEW_BYTES]
            if content_type == "text/plain" and not plain:
                plain = body[:MAX_PREVIEW_BYTES]
        elif show_images and content_type in IMAGE_MIME and len(cid_images) < 8:
            cid = (part.get("Content-ID") or "").strip("<> ")
            if cid:
                payload = part.get_payload(decode=True) or b""
                if 0 < len(payload) <= 64_000:
                    cid_images[cid.lower()] = (
                        "data:" + content_type + ";base64," +
                        base64.b64encode(payload).decode("ascii")
                    )

    # Remove executable/style blocks WITH their content before bleach. Otherwise
    # email newsletter CSS is displayed as raw text at the top of the preview.
    rich = re.sub(r"<(script|style|head|iframe|object|svg)\\b[^>]*>[\\s\\S]*?</\\1\\s*>",
                  "", rich, flags=re.I)
    has_remote_images = bool(re.search(r"<img\b[^>]*\bsrc\s*=\s*['\"]?https?://", rich, re.I))
    if rich:
        def allowed(tag, name, value):
            if name == "style":
                return len(value) <= 10000
            if tag == "a" and name in ("href", "title"):
                if name == "title":
                    return len(value) <= 300
                return value.lower().startswith(("https://", "http://", "mailto:")) and len(value) <= 2048
            if tag == "img" and name in ("src", "alt", "title", "width", "height"):
                if name in ("alt", "title"):
                    return len(value) <= 300
                if name in ("width", "height"):
                    return bool(re.fullmatch(r"\d{1,4}", value))
                if not show_images:
                    return False
                if value.lower().startswith("cid:"):
                    return value[4:].strip("<> ").lower() in cid_images
                if value.startswith("data:"):
                    return value in cid_images.values()
                return safe_image_url(value)
            if tag in ("td", "th") and name in ("colspan", "rowspan"):
                return bool(re.fullmatch(r"\d{1,2}", value))
            return False

        # Substitute only recognized embedded images, and only after explicit consent.
        if show_images:
            def replace_cid(match):
                cid = match.group(1).strip("<> ").lower()
                return html.escape(cid_images.get(cid, ""), quote=True)
            rich = re.sub(r"cid:([^'\"\s>]+)", replace_cid, rich, flags=re.I)
        sanitized = bleach.clean(
            rich, tags=ALLOWED_TAGS, attributes=allowed,
            protocols={"http", "https", "mailto", "data"}, strip=True,
            css_sanitizer=EMAIL_CSS,
        )
        if not show_images:
            sanitized = re.sub(r"<img\b[^>]*>", '<span>[Obrázek skryt]</span>', sanitized, flags=re.I)
        img_policy = "https: data:" if show_images else "'none'"
        envelope = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<meta http-equiv='Content-Security-Policy' content=\""
            "default-src 'none'; script-src 'none'; connect-src 'none'; "
            "style-src 'unsafe-inline'; img-src " + img_policy +
            "; font-src 'none'; form-action 'none'; base-uri 'none'\">"
            "<base target='_blank'><style>"
            "body{font:14px/1.65 Arial,sans-serif;color:#172019;margin:16px;"
            "overflow-wrap:anywhere;}table{max-width:100%;border-collapse:collapse}"
            "td,th{padding:4px;}img{max-width:100%;height:auto}"
            "a{color:#436c08}blockquote{border-left:3px solid #b9d98e;padding-left:10px}"
            "</style></head><body>" + sanitized + "</body></html>"
        )
        return MailPreview(envelope, plain, True, has_remote_images, truncated)

    return MailPreview("", plain or "Tento e-mail neobsahuje dostupný textový náhled.", False, False, truncated)
