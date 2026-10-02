"""Data ownership (SRD §35): export and account deletion."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import clear_auth_cookies, get_current_user
from app.core.db import get_session
from app.core.errors import AuthError
from app.core.security import verify_password
from app.core.storage import get_storage
from app.domain.persona import get_or_create_persona, serialize_persona
from app.models.generation import Generation
from app.models.ingestion import Document, Source
from app.models.persona import Persona
from app.models.user import User


async def _export_payload(session: AsyncSession, user: User, persona: Persona) -> dict[str, Any]:
    data = await serialize_persona(session, persona)
    sources = (
        await session.execute(select(Source).where(Source.persona_id == persona.id))
    ).scalars().all()
    gens = (
        await session.execute(select(Generation).where(Generation.persona_id == persona.id))
    ).scalars().all()
    return {
        "account": {
            "email": user.email,
            "name": user.name,
            "created_at": user.created_at.isoformat(),
        },
        "persona": data["persona"],
        "facts": data["facts"],
        "sources": [
            {"type": s.type, "title": s.title, "status": s.status,
             "last_synced": s.last_synced.isoformat() if s.last_synced else None}
            for s in sources
        ],
        "generations": [
            {"type": g.type, "title": g.title, "created_at": g.created_at.isoformat(),
             "output": g.output}
            for g in gens
        ],
    }


router = APIRouter(prefix="/account", tags=["account"])


@router.get("/export")
async def export_json(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    persona = await get_or_create_persona(session, user.id)
    payload = await _export_payload(session, user, persona)
    body = json.dumps(payload, indent=2, default=str)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="persona-export.json"'},
    )


@router.get("/export.zip")
async def export_zip(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    persona = await get_or_create_persona(session, user.id)
    payload = await _export_payload(session, user, persona)
    docs = (
        await session.execute(select(Document).where(Document.persona_id == persona.id))
    ).scalars().all()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("persona.json", json.dumps(payload, indent=2, default=str))
        for i, d in enumerate(docs):
            safe = (d.title or f"document-{i}").replace("/", "_").replace("\\", "_")
            zf.writestr(f"documents/{i:02d}-{safe}.txt", d.content)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="persona-export.zip"'},
    )


class DeleteAccountRequest(BaseModel):
    password: str | None = None


@router.post("/delete", status_code=204)
async def delete_account(
    body: DeleteAccountRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    # Password-protected accounts must confirm with their password.
    if user.password_hash is not None and (
        not body.password or not verify_password(body.password, user.password_hash)
    ):
        raise AuthError("Password confirmation required", code="invalid_credentials")

    persona = await get_or_create_persona(session, user.id)

    # Remove stored files for this persona, then hard-delete the user (all
    # persona data cascades via ON DELETE CASCADE).
    get_storage().delete_prefix(str(persona.id))
    await session.delete(user)
    await session.flush()

    clear_auth_cookies(response)
    response.status_code = 204
    return response
