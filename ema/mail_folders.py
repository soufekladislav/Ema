"""Bounded IMAP folder discovery, 50-header page fetch, and safe server-side MOVE.

The IMAP server owns message history. Only headers and folder references enter MariaDB.
"""
import base64
import re

from sqlalchemy import select, update
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
    stage = "LIST"
    try:
        # On first visit to a mailbox enumerate real server folders, once.
        if not db.scalar(select(MailFolder.id).where(
            MailFolder.mailbox_id == box.id, MailFolder.id != folder.id).limit(1)):
            try:
                _discover_on_client(db, box, client)
            except MailError:
                # Do not prevent INBOX reading on a server with broken LIST.
                pass
        stage = "SELECT"
        validity, total = _select(client, folder)
        if folder.name == "INBOX":
            box.server_message_count = total
        if folder.uidvalidity != validity:
            folder.uidvalidity = validity
            folder.last_uid = 0
        stage = "SEARCH"
        typ, data = client.uid("SEARCH", None, "UNDELETED")
        if typ != "OK" or not data:
            raise MailError("IMAP server odmítl vyhledání UID")
        numbers = [int(raw) for raw in (data[0] or b"").split() if raw.isdigit()]
        numbers.sort()
        eligible = [uid for uid in numbers if before_uid is None or uid < before_uid]
        selected = eligible[-limit:]
        has_more = len(eligible) > len(selected)
        cursor = min(selected) if selected else None
        if selected:
            stage = "FETCH"
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
        stage = "DATABASE"
        box.status, box.sync_error, box.last_sync = "ok", "", now()
        db.commit()
        return {"uids": selected, "has_more": has_more, "cursor": cursor,
                "uidvalidity": validity, "server_total": total}
    except Exception as ex:
        db.rollback()
        message = (str(ex) if isinstance(ex, MailError) else
                   f"Načtení IMAP selhalo ve fázi {stage} ({type(ex).__name__}). "
                   "Ověřte stav serveru a čerstvý diagnostický log.")
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


def _uid_move_or_soft_delete(client, uids, target):
    """Use RFC UID MOVE when supported; otherwise COPY then mark only source UIDs \Deleted.

    No EXPUNGE/CLOSE on source: legacy IMAP without UIDPLUS must not delete
    messages already marked \Deleted by another mail client.
    A successful COPY with failed STORE is uncertain and MUST NOT be retried.
    """
    capabilities = {word.upper() for item in getattr(client, "capabilities", [])
                    for word in (item if isinstance(item, bytes) else str(item).encode()).split()}
    if b"MOVE" in capabilities:
        result, _ = client.uid("MOVE", uids, quote_mailbox_name(target.name))
        if result != "OK":
            raise MailError("IMAP server odmítl UID MOVE; stav je nutné ověřit na serveru")
        return "move"
    result, _ = client.uid("COPY", uids, quote_mailbox_name(target.name))
    if result != "OK":
        raise MailError("IMAP odmítl kopírování do cílové složky; zdroj zůstal beze změn")
    try:
        result, _ = client.uid("STORE", uids, "+FLAGS.SILENT", r"(\Deleted)")
    except Exception:
        raise MailError("Kopie může být v cílové složce, ale označení zdroje selhalo. "
                        "Ověřte obě složky; operaci automaticky neopakujte") from None
    if result != "OK":
        raise MailError("Kopie může být v cílové složce, zdroj ale nebyl označen jako přesunutý. "
                        "Před opakováním ověřte obě složky")
    # Deliberately leave the original \Deleted on the remote server.
    return "copy-mark-deleted"


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
        validity, _ = _select(client, src)
        if validity != msg.uidvalidity:
            raise MailError("UIDVALIDITY se změnilo. Zprávu je nutné znovu načíst")
        # SELECT was readonly: reopen with write permissions before MOVE.
        typ, _ = client.select(quote_mailbox_name(src.name), readonly=False)
        if typ != "OK":
            raise MailError("Server neumožňuje zápis do zdrojové složky")
        _uid_move_or_soft_delete(client, str(msg.uid), target)
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



def move_many_messages(db, box, key, messages, action):
    """One remote UID MOVE per mailbox/source-folder batch (up to 50 UIDs)."""
    if not messages or len(messages) > 50:
        raise MailError("Dávka přesunu musí obsahovat 1–50 zpráv")
    folders = {m.folder_id for m in messages}
    if len(folders) != 1 or any(m.mailbox_id != box.id or m.moved for m in messages):
        raise MailError("Přesun vyžaduje jednu zdrojovou složku a platné zprávy")
    src = db.get(MailFolder, messages[0].folder_id)
    if src is None or src.mailbox_id != box.id or any(m.uidvalidity != src.uidvalidity for m in messages):
        raise MailError("UIDVALIDITY se změnilo; nejprve obnov zprávy")
    target = special_folder(db, box, action)
    client = _connect(box, key)
    try:
        if target is None:
            _discover_on_client(db, box, client)
            target = special_folder(db, box, action)
        if target is None:
            raise MailError("Cílová složka Koš/Archiv nebyla na IMAP serveru nalezena")
        if target.id == src.id:
            raise MailError("Zprávy jsou již v cílové složce")
        validity, _ = _select(client, src)
        if validity != src.uidvalidity:
            raise MailError("UIDVALIDITY se změnilo; obnov zprávy a operaci ověř")
        status, _ = client.select(quote_mailbox_name(src.name), readonly=False)
        if status != "OK":
            raise MailError("IMAP server neumožňuje zápis do zdrojové složky")
        uids = ",".join(str(uid) for uid in sorted({m.uid for m in messages}))
        _uid_move_or_soft_delete(client, uids, target)
        for m in messages:
            m.moved = True
        db.commit()
        return target
    except Exception as ex:
        db.rollback()
        raise MailError(str(ex) if isinstance(ex, MailError)
                        else "Hromadný přesun není potvrzen. Před opakováním ověřte IMAP") from None
    finally:
        try:
            client.logout()
        except Exception:
            pass


def empty_trash_batch(db, box, key, folder, *, limit=100):
    """Delete at most 100 messages from the verified Trash folder only.

    UIDPLUS uses targeted UID EXPUNGE. Legacy IMAP may use regular EXPUNGE
    *only* when the complete Trash fits the limit, because standard EXPUNGE
    removes every message marked Deleted in the selected folder.
    Never use regular EXPUNGE in INBOX or for a partial Trash page.
    """
    if folder.mailbox_id != box.id:
        raise MailError("Koš nepatří k vybrané schránce")
    if special_folder(db, box, "trash") is None or special_folder(db, box, "trash").id != folder.id:
        raise MailError("Vybraná složka není ověřený serverový Koš")
    limit = max(1, min(int(limit), 100))
    client = _connect(box, key)
    try:
        capabilities = {word.upper() for item in getattr(client, "capabilities", [])
                        for word in (item if isinstance(item, bytes) else str(item).encode()).split()}
        uidplus = b"UIDPLUS" in capabilities
        status, _ = client.select(quote_mailbox_name(folder.name), readonly=False)
        if status != "OK":
            raise MailError("IMAP server neumožnil otevření Koše pro mazání")
        valid_info = client.response("UIDVALIDITY")[1]
        validity = int(valid_info[0]) if valid_info and valid_info[0] else 0
        if not validity or (folder.uidvalidity and folder.uidvalidity != validity):
            raise MailError("Koš změnil UIDVALIDITY. Nejdříve obnov složku")
        status, data = client.uid("SEARCH", None, "ALL")
        if status != "OK":
            raise MailError("Nelze ověřit obsah IMAP Koše")
        all_uids = sorted(int(x) for x in (data[0] or b"").split() if x.isdigit())
        if not uidplus and len(all_uids) > limit:
            raise MailError(f"Koš obsahuje {len(all_uids)} zpráv. Server bez UIDPLUS "
                            f"neumí bezpečně smazat jen {limit} zpráv; nic nebylo smazáno.")
        selected = all_uids[:limit]
        for start in range(0, len(selected), 50):
            batch = ",".join(str(x) for x in selected[start:start+50])
            status, _ = client.uid("STORE", batch, "+FLAGS.SILENT", r"(\Deleted)")
            if status != "OK":
                raise MailError("IMAP server odmítl označení zpráv ke smazání")
            if uidplus:
                status, _ = client.uid("EXPUNGE", batch)
                if status != "OK":
                    raise MailError("IMAP server nepotvrdil cílené smazání; neopakujte bez kontroly")
                for row in db.scalars(select(MailMessage).where(
                        MailMessage.folder_id == folder.id, MailMessage.uidvalidity == validity,
                        MailMessage.uid.in_(selected[start:start+50]))).all():
                    row.moved = True
                db.commit()
        if not uidplus and selected:
            # All server Trash UIDs were explicitly selected and flagged above;
            # standard EXPUNGE is permitted only on this entire Trash folder.
            status, _ = client.expunge()
            if status != "OK":
                raise MailError("IMAP server nepotvrdil vysypání Koše. Zkontrolujte obsah před opakováním")
            for row in db.scalars(select(MailMessage).where(
                    MailMessage.folder_id == folder.id, MailMessage.uidvalidity == validity,
                    MailMessage.uid.in_(selected))).all():
                row.moved = True
            db.commit()
        return len(selected), len(all_uids) > len(selected)
    except Exception as ex:
        db.rollback()
        raise MailError(str(ex) if isinstance(ex, MailError)
                        else "Mazání Koše není potvrzené; ověřte jeho obsah na IMAP serveru") from None
    finally:
        try:
            client.logout()
        except Exception:
            pass



def _trash_selected_state(client, folder, *, readonly):
    """Verify the real server Trash and capture a precise immutable UID boundary."""
    typ, exists = client.select(quote_mailbox_name(folder.name), readonly=readonly)
    if typ != "OK":
        raise MailError("IMAP server neotevřel složku Koš")
    valid = client.response("UIDVALIDITY")[1]
    try:
        uidvalidity = int(valid[0]) if valid and valid[0] else 0
    except (ValueError, TypeError):
        uidvalidity = 0
    if not uidvalidity or (folder.uidvalidity and uidvalidity != folder.uidvalidity):
        raise MailError("UIDVALIDITY Koše se změnilo. Obnovte složku před mazáním.")
    typ, result = client.uid("SEARCH", None, "ALL")
    if typ != "OK" or not result:
        raise MailError("IMAP server nepotvrdil seznam zpráv v Koši")
    uids = [int(uid) for uid in (result[0] or b"").split() if uid.isdigit()]
    try:
        exists_count = int(exists[0])
    except (ValueError, TypeError, IndexError):
        raise MailError("Nelze ověřit počet zpráv v Koši") from None
    if exists_count != len(uids):
        raise MailError("Obsah Koše se během kontroly změnil. Načtěte počet znovu.")
    return {"count": len(uids), "uidvalidity": uidvalidity,
            "max_uid": max(uids, default=0)}


def _verify_trash_scope(db, box, folder):
    if folder.mailbox_id != box.id:
        raise MailError("Koš nepatří vybrané schránce")
    detected = special_folder(db, box, "trash")
    if not detected or detected.id != folder.id:
        raise MailError("Tato složka není ověřeným IMAP Košem dané schránky")


def preview_trash_all(db, box, key, folder):
    """Read-only snapshot for a separate, explicit all-trash confirmation page."""
    _verify_trash_scope(db, box, folder)
    client = _connect(box, key)
    try:
        return _trash_selected_state(client, folder, readonly=True)
    except Exception as ex:
        raise MailError(str(ex) if isinstance(ex, MailError) else
                        "Nepodařilo se ověřit obsah serverového Koše.") from None
    finally:
        try:
            client.logout()
        except Exception:
            pass


def empty_trash_all(db, box, key, folder, expected):
    """Delete a confirmed *entire* Trash even on legacy IMAP without UIDPLUS.

    Standard EXPUNGE is safe only in a verified Trash, not for arbitrary
    folders or subsets. One UID STORE range, one server-side EXPUNGE.
    The preview snapshot count/uidvalidity/highest UID must still match.
    """
    _verify_trash_scope(db, box, folder)
    if (not isinstance(expected, dict) or
            any(not isinstance(expected.get(k), int) or isinstance(expected.get(k), bool)
                for k in ("count", "uidvalidity", "max_uid")) or
            expected["count"] < 0 or expected["max_uid"] < 0):
        raise MailError("Neplatné potvrzení vyprázdnění Koše")
    client = _connect(box, key)
    try:
        observed = _trash_selected_state(client, folder, readonly=False)
        if observed != expected:
            raise MailError("Počet nebo UID zpráv v Koši se změnily od potvrzení. "
                            "Nic nebylo smazáno, načtěte potvrzení znovu.")
        if not observed["count"]:
            return 0
        # Never use UID 1:*: that could mark messages delivered during this request.
        # Only existing UIDs <= the last UID the user explicitly confirmed.
        sequence = f"1:{observed['max_uid']}"
        typ, _ = client.uid("STORE", sequence, "+FLAGS.SILENT", r"(\Deleted)")
        if typ != "OK":
            raise MailError("IMAP server odmítl označení Koše k výmazu. "
                            "Stav je nejistý; zkontrolujte Koš před opakováním.")
        capabilities = {word.upper() for item in getattr(client, "capabilities", [])
                        for word in (item if isinstance(item, bytes) else str(item).encode()).split()}
        if b"UIDPLUS" in capabilities:
            typ, _ = client.uid("EXPUNGE", sequence)
        else:
            # The user explicitly chose EMPTY ENTIRE TRASH (not a subset).
            # This is the sole place regular EXPUNGE is allowed.
            typ, _ = client.expunge()
        if typ != "OK":
            raise MailError("IMAP server nepotvrdil vyprázdnění Koše. "
                            "Zkontrolujte skutečný stav na serveru; automaticky neopakujte.")
        # One SQL statement, independent of how many remote messages existed.
        db.execute(update(MailMessage).where(
            MailMessage.mailbox_id == box.id,
            MailMessage.folder_id == folder.id,
            MailMessage.uidvalidity == observed["uidvalidity"],
            MailMessage.uid <= observed["max_uid"]
        ).values(moved=True))
        db.commit()
        return observed["count"]
    except Exception as ex:
        db.rollback()
        raise MailError(str(ex) if isinstance(ex, MailError)
                        else "Vyprázdnění Koše není potvrzené; ověřte stav na IMAP serveru") from None
    finally:
        try:
            client.logout()
        except Exception:
            pass
