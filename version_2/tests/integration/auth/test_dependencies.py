"""Integration tests for API authentication."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.api.dependencies import get_current_user
from app.database.models.user import User


SECRET = "integration-test-secret-that-is-long-enough"


def create_token(
    *,
    subject: str,
) -> str:
    """Create a valid integration-test JWT."""

    return jwt.encode(
        {
            "sub": subject,
            "exp": datetime.now(timezone.utc)
            + timedelta(minutes=15),
        },
        SECRET,
        algorithm="HS256",
    )


@pytest.mark.asyncio
async def test_authenticated_subject_resolves_user(
    db_session,
    monkeypatch,
) -> None:
    """A registered JWT subject should resolve to its PAIS user."""

    subject = f"auth0|{uuid4()}"

    user = User(
        email=f"auth-{uuid4()}@example.com",
        auth_subject=subject,
        display_name="Authenticated User",
    )

    db_session.add(user)
    await db_session.flush()

    monkeypatch.setattr(settings, "auth_jwt_secret", SECRET)

    from fastapi.security import HTTPAuthorizationCredentials

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=create_token(
            subject=subject,
        ),
    )

    result = await get_current_user(
        db_session=db_session,
        credentials=credentials,
    )

    assert result.id == user.id
    assert result.auth_subject == subject


@pytest.mark.asyncio
async def test_unknown_subject_is_rejected(
    db_session,
    monkeypatch,
) -> None:
    """A valid token with no corresponding PAIS user should be rejected."""

    monkeypatch.setattr(settings, "auth_jwt_secret", SECRET)

    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=create_token(
            subject=f"auth0|unknown-{uuid4()}",
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            db_session=db_session,
            credentials=credentials,
        )

    assert exc_info.value.status_code == 401
    assert (
        exc_info.value.detail
        == "Authenticated user is not registered."
    )