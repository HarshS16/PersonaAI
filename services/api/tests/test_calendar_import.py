"""Tests for calendar import connector."""

from __future__ import annotations

from httpx import AsyncClient


async def test_calendar_upload_bad_extension(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/sources/calendar/upload",
        files={"file": ("data.csv", b"some,csv,data", "text/csv")},
    )
    assert resp.status_code == 400


async def test_calendar_upload_empty(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/sources/calendar/upload",
        files={"file": ("cal.ics", b"", "text/calendar")},
    )
    assert resp.status_code == 400


def test_ics_parser() -> None:
    from app.connectors.calendar_import import parse_ics

    ics_data = b"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Team standup
DESCRIPTION:Daily sync with engineering team
DTSTART:20261001T090000Z
DTEND:20261001T091500Z
LOCATION:Zoom
ATTENDEE;CN=Alice:mailto:alice@example.com
ORGANIZER:mailto:bob@example.com
END:VEVENT
BEGIN:VEVENT
SUMMARY:1:1 with CTO
DTSTART:20261002T140000Z
STATUS:CANCELLED
END:VEVENT
END:VCALENDAR"""

    events = parse_ics(ics_data)
    assert len(events) == 1
    assert events[0].summary == "Team standup"
    assert events[0].location == "Zoom"
    assert len(events[0].attendees) >= 1
