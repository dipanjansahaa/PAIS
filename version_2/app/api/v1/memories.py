"""Authenticated personal memory management endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.api.v1.schemas.memory import (
    MemoryCorrectionRequest,
    MemoryListResponse,
    MemoryResponse,
    MemoryStatus,
    MemoryType,
)
from app.database.models.memory import Memory
from app.database.models.user import User
from app.database.session import get_db
from app.memory.service import MemoryService


router = APIRouter(prefix="/memories", tags=["memories"])


def get_memory_service() -> MemoryService:
    """Provide the memory lifecycle service."""

    return MemoryService()


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    db_session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    memory_status: Annotated[
        MemoryStatus | None, Query(alias="status")
    ] = None,
    memory_type: MemoryType | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MemoryListResponse:
    """List only the authenticated user's memories, including provenance."""

    statement = (
        select(Memory)
        .options(selectinload(Memory.sources))
        .where(Memory.user_id == current_user.id)
        .order_by(Memory.created_at.desc(), Memory.id.desc())
        .limit(limit)
        .offset(offset)
    )

    if memory_status is not None:
        statement = statement.where(Memory.status == memory_status)

    if memory_type is not None:
        statement = statement.where(Memory.memory_type == memory_type)

    result = await db_session.scalars(statement)

    return MemoryListResponse(
        items=[
            MemoryResponse.model_validate(memory)
            for memory in result.all()
        ],
        limit=limit,
        offset=offset,
    )


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: UUID,
    db_session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MemoryResponse:
    """Get one memory if it belongs to the authenticated user."""

    memory = await db_session.scalar(
        select(Memory)
        .options(selectinload(Memory.sources))
        .where(
            Memory.id == memory_id,
            Memory.user_id == current_user.id,
        )
    )

    if memory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found.",
        )

    return MemoryResponse.model_validate(memory)


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def correct_memory(
    memory_id: UUID,
    payload: MemoryCorrectionRequest,
    db_session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    memory_service: Annotated[
        MemoryService, Depends(get_memory_service)
    ],
) -> MemoryResponse:
    """Correct a memory by creating a replacement and retaining history."""

    try:
        replacement = await memory_service.update_memory(
            db_session,
            user_id=current_user.id,
            memory_id=memory_id,
            content=payload.content,
            confidence=payload.confidence,
            valid_from=payload.valid_from,
            valid_until=payload.valid_until,
            source_kind="manual_update",
            source_reference=payload.source_reference,
            evidence_text=payload.evidence_text,
        )

        await db_session.commit()

    except ValueError as exc:
        await db_session.rollback()

        message = str(exc)
        code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in message.lower()
            else status.HTTP_409_CONFLICT
        )

        raise HTTPException(
            status_code=code,
            detail=message,
        ) from exc

    except Exception:
        await db_session.rollback()
        raise

    # Reload the replacement with provenance after the transaction commits.
    result = await db_session.scalar(
        select(Memory)
        .options(selectinload(Memory.sources))
        .where(
            Memory.id == replacement.id,
            Memory.user_id == current_user.id,
        )
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The corrected memory could not be reloaded.",
        )

    return MemoryResponse.model_validate(result)


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_memory(
    memory_id: UUID,
    db_session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Permanently delete an owned memory and its provenance records."""

    memory = await db_session.scalar(
        select(Memory).where(
            Memory.id == memory_id,
            Memory.user_id == current_user.id,
        )
    )

    if memory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found.",
        )

    await db_session.delete(memory)

    try:
        await db_session.commit()
    except Exception:
        await db_session.rollback()
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)