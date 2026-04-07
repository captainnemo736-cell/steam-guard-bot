import imaplib
import email
import re

IMAP_HOST = "imap.gmail.com"

def get_steam_guard_code(email_address: str, password: str) -> str | None:
    """Connect to Gmail and fetch the latest unread Steam Guard code."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(email_address, password)
        mail.select("inbox")

        _, data = mail.search(None, '(FROM "noreply@steampowered.com" UNSEEN)')
        ids = data[0].split()

        if not ids:
            return None

        _, msg_data = mail.fetch(ids[-1], "(RFC822)")
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode()
                    break
        else:
            body = msg.get_payload(decode=True).decode()

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
