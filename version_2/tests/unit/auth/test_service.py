"""Unit tests for JWT authentication."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.auth.models import AuthenticatedIdentity
from app.auth.service import (
    AuthenticationError,
    JWTAuthenticator,
)


SECRET = "test-secret-that-is-long-enough-for-unit-tests"


def create_token(
    *,
    subject: str = "user-123",
    expires_delta: timedelta = timedelta(minutes=15),
    issuer: str | None = None,
    audience: str | None = None,
) -> str:
    """Create a deterministic test JWT."""

    payload = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + expires_delta,
    }

    if issuer is not None:
        payload["iss"] = issuer

    if audience is not None:
        payload["aud"] = audience

    return jwt.encode(
        payload,
        SECRET,
        algorithm="HS256",
    )


def test_authenticate_returns_verified_identity() -> None:
    """A valid JWT should resolve to its subject."""

    token = create_token(
        subject="auth0|user-123",
    )

    authenticator = JWTAuthenticator(
        secret=SECRET,
    )

    result = authenticator.authenticate(token)

    assert isinstance(
        result,
        AuthenticatedIdentity,
    )
    assert result.subject == "auth0|user-123"


def test_authenticate_rejects_invalid_signature() -> None:
    """A token signed with another secret must be rejected."""

    token = create_token(
        subject="user-123",
    )

    authenticator = JWTAuthenticator(
        secret="different-secret-that-is-also-long-enough",
    )

    with pytest.raises(
        AuthenticationError,
        match="Invalid authentication token",
    ):
        authenticator.authenticate(token)


def test_authenticate_rejects_expired_token() -> None:
    """Expired tokens must be rejected."""

    token = create_token(
        expires_delta=timedelta(seconds=-1),
    )

    authenticator = JWTAuthenticator(
        secret=SECRET,
    )

    with pytest.raises(
        AuthenticationError,
        match="Invalid authentication token",
    ):
        authenticator.authenticate(token)


def test_authenticate_rejects_missing_subject() -> None:
    """Tokens without a subject must be rejected."""

    payload = {
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=15),
    }

    token = jwt.encode(
        payload,
        SECRET,
        algorithm="HS256",
    )

    authenticator = JWTAuthenticator(
        secret=SECRET,
    )

    with pytest.raises(
        AuthenticationError,
        match="Invalid authentication token",
    ):
        authenticator.authenticate(token)


def test_authenticate_rejects_missing_expiration() -> None:
    """Tokens without expiration must be rejected."""

    payload = {
        "sub": "user-123",
    }

    token = jwt.encode(
        payload,
        SECRET,
        algorithm="HS256",
    )

    authenticator = JWTAuthenticator(
        secret=SECRET,
    )

    with pytest.raises(
        AuthenticationError,
        match="Invalid authentication token",
    ):
        authenticator.authenticate(token)


def test_authenticate_rejects_missing_secret() -> None:
    """Authentication must fail closed when no secret is configured."""

    authenticator = JWTAuthenticator(
        secret=None,
    )

    token = create_token()

    with pytest.raises(
        AuthenticationError,
        match="JWT authentication is not configured",
    ):
        authenticator.authenticate(token)


def test_authenticate_validates_issuer() -> None:
    """Configured issuer must match the JWT issuer."""

    token = create_token(
        issuer="https://issuer.example",
    )

    authenticator = JWTAuthenticator(
        secret=SECRET,
        issuer="https://different.example",
    )

    with pytest.raises(
        AuthenticationError,
        match="Invalid authentication token",
    ):
        authenticator.authenticate(token)


def test_authenticate_validates_audience() -> None:
    """Configured audience must match the JWT audience."""

    token = create_token(
        audience="pais-api",
    )

    authenticator = JWTAuthenticator(
        secret=SECRET,
        audience="different-api",
    )

    with pytest.raises(
        AuthenticationError,
        match="Invalid authentication token",
    ):
        authenticator.authenticate(token)


def test_authenticate_accepts_matching_issuer_and_audience() -> None:
    """Matching issuer and audience should authenticate successfully."""

    token = create_token(
        issuer="https://issuer.example",
        audience="pais-api",
    )

    authenticator = JWTAuthenticator(
        secret=SECRET,
        issuer="https://issuer.example",
        audience="pais-api",
    )

    result = authenticator.authenticate(token)

    assert result.subject == "user-123"