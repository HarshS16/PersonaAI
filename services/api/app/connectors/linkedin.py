"""LinkedIn import from the user's official data-export ZIP.

LinkedIn has no general-purpose public API, so the supported path is the user's
own data export (Settings → Get a copy of your data), which contains CSVs:
Profile.csv, Positions.csv, Skills.csv, Education.csv. We parse those into the
same structured extraction the resume pipeline produces, then merge.
"""

from __future__ import annotations

import csv
import io
import zipfile

from app.ai.extraction import (
    ExtractedEducation,
    ExtractedExperience,
    ExtractedSkill,
    ResumeExtraction,
)
from app.core.errors import AppError


def _read_csv(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    # LinkedIn nests files; match by basename, case-insensitively.
    target = next(
        (n for n in zf.namelist() if n.lower().endswith(name.lower())), None
    )
    if target is None:
        return []
    with zf.open(target) as fh:
        text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace")
        return list(csv.DictReader(text))


def _first(row: dict[str, str], *keys: str) -> str | None:
    for k in keys:
        for actual, value in row.items():
            if actual.strip().lower() == k.lower() and value.strip():
                return value.strip()
    return None


def parse_linkedin_export(data: bytes) -> ResumeExtraction:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise AppError("Not a valid LinkedIn export ZIP", code="bad_zip") from exc

    extraction = ResumeExtraction()

    profile = _read_csv(zf, "Profile.csv")
    if profile:
        p = profile[0]
        first = _first(p, "First Name") or ""
        last = _first(p, "Last Name") or ""
        extraction.full_name = (f"{first} {last}").strip() or None
        extraction.headline = _first(p, "Headline")
        extraction.summary = _first(p, "Summary")
        extraction.location = _first(p, "Geo Location", "Location")

    for row in _read_csv(zf, "Skills.csv"):
        name = _first(row, "Name", "Skill")
        if name:
            extraction.skills.append(
                ExtractedSkill(name=name, quote=f"LinkedIn skill: {name}")
            )

    for row in _read_csv(zf, "Positions.csv"):
        title = _first(row, "Title")
        if not title:
            continue
        company = _first(row, "Company Name")
        desc = _first(row, "Description")
        extraction.experiences.append(
            ExtractedExperience(
                role=title,
                company=company,
                start_date=_first(row, "Started On"),
                end_date=_first(row, "Finished On"),
                description=desc,
                quote=desc or f"{title} at {company or 'LinkedIn'}",
            )
        )

    for row in _read_csv(zf, "Education.csv"):
        school = _first(row, "School Name", "School")
        if not school:
            continue
        extraction.education.append(
            ExtractedEducation(
                institution=school,
                degree=_first(row, "Degree Name", "Degree"),
                field_of_study=_first(row, "Field Of Study"),
                quote=f"Studied at {school}",
            )
        )

    if not (extraction.skills or extraction.experiences or extraction.education):
        raise AppError(
            "No LinkedIn data found. Upload the full data-export ZIP from "
            "Settings → Get a copy of your data.",
            code="empty_linkedin",
        )
    return extraction
