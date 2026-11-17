"""Bounded IMAP folder discovery, 50-header page fetch, and safe server-side MOVE.

The IMAP server owns message history. Only headers and folder references enter MariaDB.
"""
import base64
import re

from sqlalchemy import select
from .mail_service import MailError, _connect, parse_metadata, quote_mailbox_name
from .models import MailFolder, MailMessage, now

PAGE_SIZE = 50
HEADER_REQUEST = "(UID FLAGS RFC822.SIZE BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)])"


def decode_modified_utf7(value):
    """Display IMAP modified UTF-7 names without changing server-side identifiers."""
    def convert(match):
        raw = match.group(1)
        if not raw:
            return "&"
        try:
            data = base64.b64decode(raw.replace(",", "/") + "=" * (-len(raw) % 4))
            return data.decode("utf-16-be")
        except (ValueError, UnicodeError):
            return match.group(0)
    return re.sub(r"&([A-Za-z0-9+,]*)-", convert, value)


def parse_list_line(line):
    """Parse common IMAP LIST syntax; do not trust names as filesystem paths."""
    if not isinstance(line, bytes) or len(line) > 4096:
        return None
    found = re.match(rb'^\(([^)]*)\)\s+(NIL|"(?:\\.|[^"])*")\s+(.+)$', line, re.I)
    if not found:
        return None
    flags = found.group(1).decode("ascii", "replace")[:180]
    if "\\noselect" in flags.lower():
        return None
    raw_name = found.group(3).strip()
    if raw_name.startswith(b'"') and raw_name.endswith(b'"'):
        raw_name = re.sub(rb'\\(.)', rb'\1', raw_name[1:-1])
    # Server encoded (modified UTF-7), safely usable with imaplib SELECT.
    try:
        name = raw_name.decode("ascii")
    except UnicodeDecodeError:
        return None
    if not name or len(name) > 190 or any(ch in name for ch in "\r\n\x00"):
        return None
    delim = found.group(2).decode("ascii", "replace").strip('"')[:10]
    return ("INBOX" if name.upper() == "INBOX" else name, flags, delim or "/")


def _discover_on_client(db, box, client):
    typ, data = client.list()
    if typ != "OK":
        raise MailError("IMAP server neposkytl seznam složek")
    found = []
    for row in (data or [])[:300]:
        folder = parse_list_line(row)
        if folder:
            found.append(folder)
    if not found:
        raise MailError("Server nevrátil žádné dostupné IMAP složky")
    current = {r.name: r for r in db.scalars(select(MailFolder).where(
        MailFolder.mailbox_id == box.id)).all()}
    for name, flags, delimiter in found:
        item = current.get(name)
        if item is None:
            item = MailFolder(mailbox_id=box.id, name=name, special_use=flags, delimiter=delimiter)
            db.add(item)
        else:
            item.special_use, item.delimiter = flags, delimiter
    db.flush()
    return len(found)


def discover_folders(db, box, key):
    """Explicit discovery. Does not delete previously indexed folders."""
    client = _connect(box, key)
    try:
        count = _discover_on_client(db, box, client)
        db.commit()
        return count
    except MailError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise MailError("Načtení seznamu složek selhalo") from None
    finally:
        try:
            client.logout()
        except Exception:
            pass


def available_folders(db, box):
    rows = db.scalars(select(MailFolder).where(MailFolder.mailbox_id == box.id)).all()
    return sorted(rows, key=lambda x: (x.name.upper() != "INBOX", decode_modified_utf7(x.name).casefold()))


def _select(client, folder):
    if folder.name == "INBOX":
        remote_name = "INBOX"
    else:
        remote_name = folder.name
    typ, info = client.select(quote_mailbox_name(remote_name), readonly=True)
    if typ != "OK":
        raise MailError("IMAP složku nelze otevřít")
    validity = client.response("UIDVALIDITY")[1]
    try:
        validity_id = int(validity[0]) if validity and validity[0] else 0
    except (ValueError, TypeError):
        validity_id = 0
    if validity_id <= 0:
        raise MailError("IMAP server neposkytuje UIDVALIDITY")
    return validity_id, int(info[0]) if info and info[0] is not None else 0


def fetch_folder_page(db, box, key, folder, *, before_uid=None, limit=PAGE_SIZE):
    """Fetch exactly one bounded page of headers; cursor is the remote UID, not SQL offset."""
    if folder.mailbox_id != box.id:
        raise MailError("Složka nepatří této schránce")
    limit = max(1, min(int(limit), PAGE_SIZE))
    if before_uid is not None and (not isinstance(before_uid, int) or before_uid <= 0):
        raise MailError("Neplatná stránkovací pozice")
    client = _connect(box, key)
    try:
        # On first visit to a mailbox enumerate real server folders, once.
        if not db.scalar(select(MailFolder.id).where(
            MailFolder.mailbox_id == box.id, MailFolder.id != folder.id).limit(1)):
            try:
                _discover_on_client(db, box, client)
            except MailError:
                # Do not prevent INBOX reading on a server with broken LIST.
                pass
        validity, total = _select(client, folder)
        if folder.name == "INBOX":
            box.server_message_count = total
        if folder.uidvalidity != validity:
            folder.uidvalidity = validity
            folder.last_uid = 0
        typ, data = client.uid("SEARCH", None, "ALL")
        if typ != "OK" or not data:
            raise MailError("IMAP server odmítl vyhledání UID")
        numbers = [int(raw) for raw in (data[0] or b"").split() if raw.isdigit()]
        numbers.sort()
        eligible = [uid for uid in numbers if before_uid is None or uid < before_uid]
        selected = eligible[-limit:]
        has_more = len(eligible) > len(selected)
        cursor = min(selected) if selected else None
        if selected:
            typ, response = client.uid("FETCH", ",".join(str(uid) for uid in selected), HEADER_REQUEST)
            if typ != "OK":
                raise MailError("IMAP server odmítl načtení hlaviček")
            uid_set = set(selected)
            saved_uids = set()
            for item in response or []:
                if not isinstance(item, tuple) or len(item) < 2:
                    continue
                head = item[0] if isinstance(item[0], bytes) else b""
                found = re.search(rb"\bUID\s+(\d+)\b", head, re.I)
                if not found:
                    continue
                uid = int(found.group(1))
                if uid not in uid_set:
                    continue
                msg = parse_metadata([item], uid, box.id, folder.id, validity)
                existing = db.scalar(select(MailMessage).where(
                    MailMessage.folder_id == folder.id,
                    MailMessage.uidvalidity == validity, MailMessage.uid == uid))
                if existing:
                    existing.flags = msg.flags
                    existing.moved = False
                else:
                    # Keep project/client links after an IMAP MOVE by matching a
                    # single moved record from the same mailbox and Message-ID.
                    prior = None
                    if msg.message_id:
                        rows = db.scalars(select(MailMessage).where(
                            MailMessage.mailbox_id == box.id,
                            MailMessage.message_id == msg.message_id,
                            MailMessage.moved.is_(True)).limit(2)).all()
                        if len(rows) == 1:
                            prior = rows[0]
                    if prior:
                        prior.folder_id, prior.uidvalidity, prior.uid = folder.id, validity, uid
                        prior.moved, prior.flags = False, msg.flags
                    else:
                        db.add(msg)
                saved_uids.add(uid)
            # A message can disappear between SEARCH and FETCH; no extra UID fetch.
            folder.last_uid = max(folder.last_uid, max(selected))
        box.status, box.sync_error, box.last_sync = "ok", "", now()
        db.commit()
        return {"uids": selected, "has_more": has_more, "cursor": cursor,
                "uidvalidity": validity, "server_total": total}
    except Exception as ex:
        db.rollback()
        message = str(ex) if isinstance(ex, MailError) else "Načtení zpráv z IMAP složky selhalo"
        box.status, box.sync_error = "error", message[:380]
        db.commit()
        raise MailError(message) from None
    finally:
        try:
            client.logout()
        except Exception:
            pass


def special_folder(db, box, action):
    """Resolve a real IMAP destination; favor SPECIAL-USE, then known folder leaves.

    Names may be hierarchical (INBOX.Trash, INBOX/Sent), and the delimiter
    must come from LIST rather than assuming a slash.
    """
    folders = available_folders(db, box)
    flags = {"trash": r"\Trash", "archive": r"\Archive", "sent": r"\Sent"}
    flag = flags.get(action, "").lower()
    if flag:
        by_flag = [f for f in folders if flag in (f.special_use or "").lower().split()]
        if by_flag:
            return by_flag[0]
    if action == "archive":
        by_all = [f for f in folders if r"\all" in (f.special_use or "").lower().split()]
        if by_all:
            return by_all[0]
    names = {
        "trash": {"trash", "deleted messages", "deleted items", "deleted", "koš", "kos", "bin"},
        "archive": {"archive", "archiv"},
        "sent": {"sent", "sent items", "sent mail", "odeslané", "odeslane", "odeslaná pošta"},
    }.get(action, set())
    for f in folders:
        decoded = decode_modified_utf7(f.name).casefold()
        delimiter = f.delimiter or "/"
        if decoded.rsplit(delimiter, 1)[-1] in names:
            return f
    return None


def move_message(db, box, key, msg, action):
    """Explicit server-side MOVE only. Trash never implies EXPUNGE or permanent deletion."""
    if msg.mailbox_id != box.id or msg.moved:
        raise MailError("Tato zpráva již byla přesunuta nebo není ve schránce")
    src = db.get(MailFolder, msg.folder_id)
    if src is None or src.mailbox_id != box.id or src.uidvalidity != msg.uidvalidity:
        raise MailError("Složka nebo UID zprávy se změnily. Nejdříve obnovte přehled")
    target = special_folder(db, box, action)
    client = _connect(box, key)
    try:
        # Folder LIST may not have run yet (especially on imported mailboxes).
        if target is None:
            _discover_on_client(db, box, client)
            target = special_folder(db, box, action)
        if target is None:
            raise MailError("Cílová složka Koš/Archiv nebyla na IMAP serveru nalezena; zkontrolujte názvy složek.")
        if target.id == src.id:
            raise MailError("Zpráva je již v cílové složce")
        capabilities = {word.upper() for item in getattr(client, "capabilities", [])
                        for word in (item if isinstance(item, bytes) else str(item).encode()).split()}
        if b"MOVE" not in capabilities:
            raise MailError("Server nepodporuje bezpečný přesun UID MOVE; schránka se nezměnila")
        validity, _ = _select(client, src)
        if validity != msg.uidvalidity:
            raise MailError("UIDVALIDITY se změnilo. Zprávu je nutné znovu načíst")
        # SELECT was readonly: reopen with write permissions before MOVE.
        typ, _ = client.select(quote_mailbox_name(src.name), readonly=False)
        if typ != "OK":
            raise MailError("Server neumožňuje zápis do zdrojové složky")
        typ, _ = client.uid("MOVE", str(msg.uid), quote_mailbox_name(target.name))
        if typ != "OK":
            raise MailError("IMAP server přesun zprávy odmítl")
        # No EXPUNGE, no action on the user's other mail. Keep original row for
        # future UID reconciliation and its linked project, client and user flag.
        msg.moved = True
        db.commit()
        return target
    except Exception as ex:
        db.rollback()
        raise MailError(str(ex) if isinstance(ex, MailError)
                        else "Přesun IMAP zprávy není potvrzen; ověřte ji na serveru") from None
    finally:
        try:
            client.logout()
        except Exception:
            pass



def append_sent_copy(db, box, key, raw_message):
    """After confirmed SMTP send, store a copy in the *actual* remote Sent folder.

    This must never trigger a second SMTP attempt. A failed APPEND means sent
    without a confirmed copy, not failed mail delivery.
    """
    if not raw_message or len(raw_message) > 25_000_000:
        raise MailError("Odeslaná zpráva nemá platný formát pro uložení kopie")
    client = _connect(box, key)
    try:
        _discover_on_client(db, box, client)
        destination = special_folder(db, box, "sent")
        if destination is None:
            raise MailError("Na IMAP serveru není rozpoznána složka Odeslané")
        status, _ = client.append(quote_mailbox_name(destination.name), r"(\Seen)", None, raw_message)
        if status != "OK":
            raise MailError("IMAP server odmítl uložit kopii do složky Odeslané")
        db.commit()
        return destination
    except Exception as ex:
        db.rollback()
        raise MailError(str(ex) if isinstance(ex, MailError)
                        else "Kopii odeslaného e-mailu se nepodařilo uložit do IMAP") from None
    finally:
        try:
            client.logout()
        except Exception:
            pass
