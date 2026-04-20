import imaplib
import email
import re

IMAP_HOST = "imap.gmail.com"

# Only this Steam message type indicates a login Steam Guard code.
# CAccountRecoveryCodeEmail = credential change code (we ignore these)
LOGIN_MESSAGE_TYPE = "CEmailSteamGuard_Computer"


def _is_login_email(msg) -> bool:
    """Check the X-Steam-Message-Type header to identify login emails."""
    steam_type = msg.get("X-Steam-Message-Type", "")
    return steam_type.strip() == LOGIN_MESSAGE_TYPE


def get_steam_guard_code(email_address: str, password: str) -> str | None:
    """Fetch the latest Steam Guard login code from Gmail.
    
    Only returns codes from login emails (CEmailSteamGuard_Computer).
    Credential-change emails (CAccountRecoveryCodeEmail) are ignored.
    """
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

            # Filter by Steam message type header — language-independent
            if not _is_login_email(msg):
                continue

            # Extract the code from the email body
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
