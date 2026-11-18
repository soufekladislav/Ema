"""Compose helpers: sanitized per-mailbox HTML signature and server-sourced reply quote.

Never persist message bodies or original MIME data in the database.
"""
import html
import re
from email import policy
from email.parser import BytesParser

import bleach

from .mail_render import EMAIL_CSS, safe_image_url
from .mail_service import MailError, fetch_message_mime


SIGNATURE_TAGS = {"p", "div", "span", "br", "strong", "b", "em", "i", "u",
                  "a", "img", "small", "table", "tbody", "tr", "td", "hr"}
MAX_SIGNATURE = 12000
MAX_QUOTE = 60000


def clean_signature(value):
    value = (value or "").strip()
    if len(value) > MAX_SIGNATURE:
        raise ValueError("Podpis může mít nejvýše 12 000 znaků")
    if not value:
        return ""
    if not re.search(r"<[a-zA-Z][^>]*>", value):
        return "<div>" + html.escape(value).replace("\n", "<br>") + "</div>"

    def allowed(tag, name, attr):
        if tag == "a" and name == "href":
            return attr.startswith(("https://", "mailto:")) and len(attr) < 1000
        if tag == "img" and name == "src":
            return safe_image_url(attr)
        if tag == "img" and name in ("alt", "width", "height"):
            return len(attr) <= 200 and (name == "alt" or attr.isdigit())
        if name == "style":
            return bool(EMAIL_CSS) and len(attr) <= 900 and not re.search(
                r"(?i)url\s*\(|@|expression\s*\(|\\\\", attr)
        return False

    return bleach.clean(value, tags=SIGNATURE_TAGS, attributes=allowed,
                        protocols={"https", "mailto"}, strip=True,
                        css_sanitizer=EMAIL_CSS)


def signature_as_text(cleaned_html):
    content = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", cleaned_html or "")
    content = re.sub(r"(?i)</(?:p|div|tr)>", "\n", content)
    content = bleach.clean(content, tags=set(), strip=True)
    return html.unescape(content).strip()


def outgoing_parts(body, signature_html="", quote=""):
    """Return plain and HTML alternatives, original quote is always *last*."""
    sig = clean_signature(signature_html)
    plain = body.rstrip()
    rich = "<div style='white-space:pre-wrap'>" + html.escape(plain) + "</div>"
    if sig:
        plain += "\n\n-- \n" + signature_as_text(sig)
        rich += "<div class='ema-signature'>" + sig + "</div>"
    if quote:
        plain += "\n\n" + quote
        rich += ("<hr><pre style='font:inherit;white-space:pre-wrap;"
                 "overflow-wrap:anywhere'>" + html.escape(quote) + "</pre>")
    if len(plain) > 100000:
        raise MailError("Odpověď včetně původní zprávy a podpisu překračuje limit 100 000 znaků.")
    html_body = "<!doctype html><html><head><meta charset='utf-8'></head><body>" + rich + "</body></html>"
    return plain, html_body


def original_reply_quote(box, row, key, folder_name):
    """Load original text from IMAP at reply time, not from local SQL metadata."""
    raw = fetch_message_mime(box, row, key, folder_name=folder_name)
    message = BytesParser(policy=policy.default).parsebytes(raw)
    part = message.get_body(preferencelist=("plain", "html"))
    if part is None:
        raise MailError("Původní zpráva nemá čitelný text; odpověď bez citace není povolena.")
    try:
        content = part.get_content()
    except Exception:
        content = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
    if not isinstance(content, str):
        content = content.decode("utf-8", "replace")
    if part.get_content_type() == "text/html":
        # Preserve basic line boundaries, never carry remote tags/scripts to reply.
        content = re.sub(r"(?is)<(script|style|head)\b[^>]*>.*?</\1\s*>", "", content)
        content = re.sub(r"(?i)<\s*br\s*/?\s*>|</(?:p|div|tr|h[1-6])>", "\n", content)
        content = html.unescape(bleach.clean(content, tags=set(), strip=True))
    content = content.strip()
    if len(content) > MAX_QUOTE:
        raise MailError("Původní zpráva je příliš dlouhá pro bezpečnou úplnou citaci. "
                        "Použij původní webmail nebo rozděl odpověď.")
    sent = row.sent_at.strftime("%d.%m.%Y %H:%M") if row.sent_at else "—"
    header = (f"--- Původní zpráva ---\nOd: {row.sender}\n"
              f"Komu: {row.recipients}\nDatum: {sent}\n"
              f"Předmět: {row.subject}\n\n")
    quoted = "\n".join("> " + line for line in content.splitlines())
    return header + quoted
