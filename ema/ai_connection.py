"""Server-only Fresh AI Engine configuration, no credential ever reaches browser."""
from cryptography.fernet import InvalidToken
from .mail_service import encrypt_password, decrypt_password, MailError
from .assistant_service import AssistantError, run_assistant


def seal_connector_key(value, encryption_key):
    value = (value or "").strip()
    if not 20 <= len(value) <= 512 or any(c.isspace() for c in value):
        raise AssistantError("Vlož platný API klíč (20 až 512 znaků, bez mezer).")
    try:
        return encrypt_password(value, encryption_key)
    except (MailError, ValueError, InvalidToken):
        raise AssistantError("Na serveru není připravené bezpečné šifrování. Zkontroluj MAIL_ENCRYPTION_KEY.") from None


def reveal_connector_key(connection, encryption_key):
    if connection is None or not connection.encrypted_key or not connection.verified:
        raise AssistantError("AI Engine zatím nebyl připojen a ověřen v Superadminu.")
    try:
        return decrypt_password(connection.encrypted_key, encryption_key)
    except (MailError, InvalidToken, ValueError, UnicodeError):
        raise AssistantError("Uložený AI klíč nelze rozšifrovat. Ověř původní šifrovací klíč na serveru.") from None


def verify_connector_key(value, base_url):
    """One EXPLICIT billable authenticated Engine request; never retry."""
    result = run_assistant(
        key=value, base_url=base_url,
        user_id=0, project_id=None,
        question="Test připojení aplikace EMA. Odpověz pouze jedním slovem OK.",
        projects=[], tasks=[], recent_turns=(),
    )
    if not result.strip():
        raise AssistantError("Engine nevydal žádnou odpověď.")
    return True
