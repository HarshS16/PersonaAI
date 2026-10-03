"""Email import: parse MBOX and .eml files into structured messages.

Only SENT emails are kept, since outgoing messages reflect the user's
communication style, expertise, and professional interests. Bodies are
stripped of HTML and capped to avoid runaway token usage.
"""

from __future__ import annotations

import email
import email.policy
import email.utils
import mailbox
import re
import tempfile
from dataclasses import dataclass, field
from html.parser import HTMLParser

MAX_BODY_CHARS = 2000
MAX_EMAILS = 500


@dataclass
class EmailMessage:
    subject: str
    sender: str
    recipients: list[str] = field(default_factory=list)
    date: str | None = None
    body_text: str = ""
    is_sent: bool = False


# ---------------------------------------------------------------------------
# HTML stripping
# ---------------------------------------------------------------------------

class _HTMLStripper(HTMLParser):
    """Minimal HTML-to-text converter."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def _strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    try:
        stripper.feed(html)
    except Exception:  # noqa: BLE001
        # Fall back to crude regex strip on malformed HTML.
        return re.sub(r"<[^>]+>", "", html)
    return stripper.get_text()


# ---------------------------------------------------------------------------
# Body extraction
# ---------------------------------------------------------------------------

def _extract_body(msg: email.message.Message) -> str:
    """Return the plain-text body of an email, stripping HTML if needed."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body = payload.decode(charset, errors="replace")
                    except (LookupError, UnicodeDecodeError):
                        body = payload.decode("utf-8", errors="replace")
                    break
            elif ct == "text/html" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        raw = payload.decode(charset, errors="replace")
                    except (LookupError, UnicodeDecodeError):
                        raw = payload.decode("utf-8", errors="replace")
                    body = _strip_html(raw)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                raw = payload.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                raw = payload.decode("utf-8", errors="replace")
            body = _strip_html(raw) if msg.get_content_type() == "text/html" else raw

    # Collapse whitespace and cap length.
    body = re.sub(r"\s+", " ", body).strip()
    return body[:MAX_BODY_CHARS]


# ---------------------------------------------------------------------------
# Address helpers
# ---------------------------------------------------------------------------

def _addr(header: str | None) -> str:
    """Extract bare email address from a header value."""
    if not header:
        return ""
    _, addr = email.utils.parseaddr(header)
    return addr.lower()


def _addr_list(header: str | None) -> list[str]:
    if not header:
        return []
    pairs = email.utils.getaddresses([header])
    return [addr.lower() for _, addr in pairs if addr]


# ---------------------------------------------------------------------------
# Single .eml parsing
# ---------------------------------------------------------------------------

def _to_email_message(
    msg: email.message.Message,
    user_addr: str | None = None,
) -> EmailMessage:
    sender = _addr(msg.get("From", ""))
    to_addrs = _addr_list(msg.get("To", ""))
    cc_addrs = _addr_list(msg.get("Cc", ""))
    recipients = to_addrs + cc_addrs

    # Determine if this is a sent email.
    is_sent = False
    if user_addr:
        is_sent = sender == user_addr.lower()
    else:
        # Heuristic: emails in "Sent" folder or X-Folder header.
        x_folder = msg.get("X-Folder", "") or msg.get("X-Gmail-Labels", "")
        if re.search(r"(?i)\bsent\b", x_folder):
            is_sent = True

    date_str: str | None = None
    raw_date = msg.get("Date")
    if raw_date:
        parsed = email.utils.parsedate_to_datetime(raw_date)
        if parsed:
            date_str = parsed.isoformat()

    return EmailMessage(
        subject=str(msg.get("Subject", "")).strip(),
        sender=sender,
        recipients=recipients,
        date=date_str,
        body_text=_extract_body(msg),
        is_sent=is_sent,
    )


def parse_eml(data: bytes) -> EmailMessage:
    """Parse a single .eml file into an EmailMessage."""
    msg = email.message_from_bytes(data, policy=email.policy.default)
    em = _to_email_message(msg)
    # A standalone .eml uploaded by the user is assumed to be theirs.
    em.is_sent = True
    return em


# ---------------------------------------------------------------------------
# MBOX parsing
# ---------------------------------------------------------------------------

def parse_mbox(data: bytes) -> list[EmailMessage]:
    """Parse an MBOX file and return only sent emails (up to MAX_EMAILS).

    The first sender address encountered is assumed to be the user's address
    for sent-mail filtering.
    """
    # mailbox.mbox requires a real file path, so write to a temp file.
    with tempfile.NamedTemporaryFile(suffix=".mbox", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    mbox = mailbox.mbox(tmp_path)

    # First pass: detect the user's address from the most common sender.
    sender_counts: dict[str, int] = {}
    for msg in mbox:
        addr = _addr(msg.get("From", ""))
        if addr:
            sender_counts[addr] = sender_counts.get(addr, 0) + 1

    user_addr: str | None = None
    if sender_counts:
        user_addr = max(sender_counts, key=sender_counts.get)  # type: ignore[arg-type]

    # Second pass: collect sent emails.
    results: list[EmailMessage] = []
    mbox = mailbox.mbox(tmp_path)  # re-open iterator
    for msg in mbox:
        em = _to_email_message(msg, user_addr=user_addr)
        if not em.is_sent:
            continue
        results.append(em)
        if len(results) >= MAX_EMAILS:
            break

    import contextlib
    import os

    with contextlib.suppress(OSError):
        os.unlink(tmp_path)

    return results
