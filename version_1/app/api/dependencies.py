"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User
from app.database.session import get_db


__all__ = ["get_db", "get_current_user"]


async def get_current_user(
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Return the development user until authentication is implemented."""

    result = await db_session.execute(
        select(User)
        .where(User.email == "dev@pais.local")
        .limit(1)
    )

    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email="dev@pais.local",
            display_name="PAIS Development User",
        )
        db_session.add(user)
        await db_session.flush()

    return user