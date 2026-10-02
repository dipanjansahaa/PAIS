"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthenticationError, JWTAuthenticator
from app.database.models.user import User
from app.database.session import get_db


__all__ = [
    "get_db",
    "get_current_user",
]


_bearer_scheme = HTTPBearer(
    auto_error=False,
)


async def get_current_user(
    db_session: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> User:
    """Resolve the authenticated PAIS user from a JWT bearer token."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials are required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        identity = JWTAuthenticator().authenticate(
            credentials.credentials,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    result = await db_session.execute(
        select(User)
        .where(User.auth_subject == identity.subject)
        .limit(1)
    )

    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user is not registered.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user