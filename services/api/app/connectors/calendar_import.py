"""ICS calendar file parser.

Parses .ics (iCalendar) files by extracting VEVENT blocks manually,
without any external dependency.  Handles line folding, common
properties (SUMMARY, DESCRIPTION, DTSTART, DTEND, LOCATION, ATTENDEE,
ORGANIZER), and skips cancelled events.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.errors import AppError

MAX_EVENTS = 1000

# Regex to pull the "value" after a property name (and optional params).
_PROP_RE = re.compile(
    r"^([A-Z\-]+)"   # property name
    r"(?:;[^:]+)?"    # optional parameters (;TZID=... etc.)
    r":(.*)",          # colon + value
    re.DOTALL,
)


@dataclass
class CalendarEvent:
    summary: str
    description: str | None = None
    start: str | None = None
    end: str | None = None
    location: str | None = None
    attendees: list[str] = field(default_factory=list)
    organizer: str | None = None


def _unfold_lines(text: str) -> list[str]:
    """RFC 5545 line unfolding: a CRLF followed by a space/tab
    is a continuation of the previous line."""
    # Normalise to \n then rejoin continuation lines.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for raw in text.split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _extract_value(line: str) -> tuple[str, str] | None:
    """Return (PROPERTY_NAME, value) or None."""
    m = _PROP_RE.match(line)
    if m:
        return m.group(1).upper(), m.group(2)
    return None


def _extract_email(value: str) -> str:
    """Strip 'mailto:' prefix if present."""
    if value.lower().startswith("mailto:"):
        return value[7:].strip()
    return value.strip()


def _parse_vevent(lines: list[str]) -> CalendarEvent | None:
    """Parse a single VEVENT block into a CalendarEvent."""
    props: dict[str, str] = {}
    attendees: list[str] = []

    for line in lines:
        pair = _extract_value(line)
        if pair is None:
            continue
        name, val = pair
        if name == "ATTENDEE":
            email = _extract_email(val)
            if email:
                attendees.append(email)
        elif name == "ORGANIZER":
            props["ORGANIZER"] = _extract_email(val)
        elif name not in props:
            # Keep first occurrence of each property.
            props[name] = val

    # Skip cancelled events.
    if props.get("STATUS", "").upper() == "CANCELLED":
        return None

    summary = props.get("SUMMARY", "").strip()
    if not summary:
        return None

    description = props.get("DESCRIPTION")
    if description:
        # Unescape common ICS escape sequences.
        description = (
            description
            .replace("\\n", "\n")
            .replace("\\N", "\n")
            .replace("\\,", ",")
            .replace("\\;", ";")
            .replace("\\\\", "\\")
            .strip()
        )

    return CalendarEvent(
        summary=summary,
        description=description or None,
        start=props.get("DTSTART"),
        end=props.get("DTEND"),
        location=props.get("LOCATION") or None,
        attendees=attendees,
        organizer=props.get("ORGANIZER"),
    )


def parse_ics(data: bytes) -> list[CalendarEvent]:
    """Parse raw ICS bytes into a list of CalendarEvent objects.

    Raises AppError when the data is clearly not an ICS file.
    Returns at most MAX_EVENTS events.
    """
    text = data.decode("utf-8", errors="replace")
    if "BEGIN:VCALENDAR" not in text:
        raise AppError(
            "Not a valid ICS calendar file",
            code="bad_ics",
        )

    unfolded = _unfold_lines(text)

    # Split into VEVENT blocks.
    events: list[CalendarEvent] = []
    in_event = False
    event_lines: list[str] = []

    for line in unfolded:
        stripped = line.strip()
        if stripped == "BEGIN:VEVENT":
            in_event = True
            event_lines = []
        elif stripped == "END:VEVENT" and in_event:
            in_event = False
            ev = _parse_vevent(event_lines)
            if ev is not None:
                events.append(ev)
                if len(events) >= MAX_EVENTS:
                    break
        elif in_event:
            event_lines.append(line)

    if not events:
        raise AppError(
            "No calendar events found in the file",
            code="empty_calendar",
        )

    return events
