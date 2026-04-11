import imaplib
import email
import re
from email.header import decode_header as _decode_header

IMAP_HOST = "imap.gmail.com"

# Subjects that indicate a Steam Guard LOGIN code (not credential changes)
LOGIN_SUBJECTS = [
    "your steam account: access from new",
    "steam guard",
    "new computer",
    "new device",
]

def _get_subject(msg) -> str:
    subject = msg.get("Subject", "")
    decoded, enc = _decode_header(subject)[0]
    if isinstance(decoded, bytes):
        return decoded.decode(enc or "utf-8", errors="ignore").lower()
    return decoded.lower()

def _is_login_email(msg) -> bool:
    subject = _get_subject(msg)
    return any(keyword in subject for keyword in LOGIN_SUBJECTS)

def get_steam_guard_code(email_address: str, password: str) -> str | None:
    """Fetch the latest Steam Guard login code from Gmail."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(email_address, password)
        mail.select("inbox")

        # Search all emails from Steam (read and unread)
        _, data = mail.search(None, '(FROM "noreply@steampowered.com")')
        ids = data[0].split()

        if not ids:
            return None

        # Check from latest to oldest, find first login code email
        for id in reversed(ids):
            _, msg_data = mail.fetch(id, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            if not _is_login_email(msg):
                continue

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")

            match = re.search(r'\b([A-Z0-9]{5})\b', body)
            if match:
                return match.group(1)

        return None

    except Exception as e:
        raise RuntimeError(f"IMAP error: {e}")
    finally:
        try:
            mail.logout()
        except Exception:
            pass
