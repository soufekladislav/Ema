"""Server-only Fresh AI Engine connector configuration and explicit paid verification.

The PUBLIC /v1/health never authenticates a connector key. An explicit
/v1/engine/run probe does. Never log, export or return raw tokens.
"""
import json
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken

class EngineConfigError(Exception):
    """Generic, non-sensitive configuration or remote transport failure."""


def secure_base_url(base):
    p = urlsplit((base or "").rstrip("/"))
    if p.scheme != "https" or p.hostname != "aiengine.freshcrackers.cz" or p.port not in (None, 443) or p.username or p.password or p.query or p.fragment or p.path:
        raise EngineConfigError("Fresh AI Engine musí používat oficiální HTTPS adresu.")
    return "https://aiengine.freshcrackers.cz"


def encrypt_engine_key(key, encryption_key):
    if not isinstance(key, str) or not 24 <= len(key) <= 512 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise EngineConfigError("Neplatný formát přístupového klíče.")
    try:
        return Fernet(encryption_key.encode("ascii")).encrypt(key.encode("utf-8")).decode("ascii")
    except (ValueError, TypeError, AttributeError):
        raise EngineConfigError("Na serveru není platný MAIL_ENCRYPTION_KEY pro zašifrování klíče.") from None


def decrypt_engine_key(cipher, encryption_key):
    try:
        return Fernet(encryption_key.encode("ascii")).decrypt(cipher.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError, AttributeError):
        raise EngineConfigError("Uložený klíč nelze bezpečně dešifrovat; zkontrolujte šifrovací konfiguraci.") from None


def verify_engine_key(key, base_url, *, timeout=18):
    """One explicitly requested, billable POST, no retries and no raw text."""
    url = secure_base_url(base_url) + "/v1/engine/run"
    payload = {
        "source": "ema",
        "task_type": "general",
        "operation": "ema.connector.verify",
        "quality": "economy",
        "prompt": "Odpověz jedním slovem OK. Toto je ověření propojení Emy s Fresh AI Engine.",
        "max_output_tokens": 24,
    }
    request = Request(url, method="POST",
                      data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      headers={"Authorization": "Bearer " + key,
                               "Content-Type": "application/json",
                               "Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status < 200 or response.status >= 300:
                return False, response.status, "remote_failure"
            data = response.read(32769)
    except HTTPError as exc:
        code = int(exc.code)
        category = {400: "bad_request", 401: "invalid_key",
                    402: "insufficient_credits", 403: "forbidden",
                    422: "invalid_payload"}.get(code, "service_error")
        return False, code, category
    except (URLError, TimeoutError, OSError):
        return False, None, "network_or_timeout"
    if len(data) > 32768:
        return False, None, "invalid_response"
    try:
        response = json.loads(data)
    except (UnicodeError, ValueError):
        return False, None, "invalid_response"
    if isinstance(response, dict) and response.get("status") == "completed":
        # We intentionally do not persist the AI output or its accounting data.
        return True, 200, "verified"
    return False, 200, "incomplete_response"
