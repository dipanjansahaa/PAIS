"""Unit tests for shared API dependencies."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.dependencies import get_current_user
from app.database.models.user import User


SECRET = "test-secret-that-is-long-enough-for-unit-tests"


def create_token(
    *,
    subject: str,
) -> str:
    """Create a valid test JWT."""

    return jwt.encode(
        {
            "sub": subject,
            "exp": datetime.now(timezone.utc)
            + timedelta(minutes=15),
        },
        SECRET,
        algorithm="HS256",
    )


class FakeResult:
    """Minimal SQLAlchemy result fake."""

    def __init__(
        self,
        user: User | None,
    ) -> None:
        self.user = user

    def scalar_one_or_none(self):
        return self.user


class FakeSession:
    """Minimal async database session fake."""

    def __init__(
        self,
        user: User | None,
    ) -> None:
        self.user = user

    async def execute(self, statement):
        return FakeResult(self.user)


@pytest.mark.asyncio
async def test_get_current_user_returns_authenticated_user(
    monkeypatch,
) -> None:
    """A valid token should resolve the matching PAIS user."""

    user = User(
        id=uuid4(),
        email="user@example.com",
        auth_subject="auth0|user-123",
        display_name="Test User",
    )

    monkeypatch.setattr(
        "app.api.dependencies.JWTAuthenticator",
        lambda: _FixedAuthenticator("auth0|user-123"),
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="valid-token",
    )

    result = await get_current_user(
        db_session=FakeSession(user),
        credentials=credentials,
    )

    assert result is user


@pytest.mark.asyncio
async def test_get_current_user_requires_credentials() -> None:
    """Requests without credentials should receive HTTP 401."""

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            db_session=FakeSession(None),
            credentials=None,
        )

    assert exc_info.value.status_code == 401
    assert (
        exc_info.value.headers["WWW-Authenticate"]
        == "Bearer"
    )


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_token(
    monkeypatch,
) -> None:
    """Invalid authentication tokens should receive HTTP 401."""

    from app.auth.service import AuthenticationError

    class FailingAuthenticator:
        def authenticate(self, token: str):
            raise AuthenticationError(
                "Invalid authentication token.",
            )

    monkeypatch.setattr(
        "app.api.dependencies.JWTAuthenticator",
        FailingAuthenticator,
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="invalid-token",
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            db_session=FakeSession(None),
            credentials=credentials,
        )

    assert exc_info.value.status_code == 401
    assert (
        exc_info.value.detail
        == "Invalid authentication token."
    )


@pytest.mark.asyncio
async def test_get_current_user_rejects_unknown_subject(
    monkeypatch,
) -> None:
    """A valid JWT for an unregistered subject should receive HTTP 401."""

    monkeypatch.setattr(
        "app.api.dependencies.JWTAuthenticator",
        lambda: _FixedAuthenticator("unknown-user"),
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="valid-token",
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            db_session=FakeSession(None),
            credentials=credentials,
        )

    assert exc_info.value.status_code == 401
    assert (
        exc_info.value.detail
        == "Authenticated user is not registered."
    )


class _FixedAuthenticator:
    """Authenticator fake returning a predetermined subject."""

    def __init__(
        self,
        subject: str,
    ) -> None:
        self.subject = subject

    def authenticate(
        self,
        token: str,
    ):
        from app.auth.models import AuthenticatedIdentity

        return AuthenticatedIdentity(
            subject=self.subject,
        )