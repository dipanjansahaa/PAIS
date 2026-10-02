"""JWT authentication services."""

from __future__ import annotations

from typing import Any

import jwt
from jwt import InvalidTokenError

from app.auth.models import AuthenticatedIdentity
from app.core.config import settings


class AuthenticationError(Exception):
    """Raised when authentication credentials are invalid."""


_UNSET = object()


class JWTAuthenticator:
    """Verify HS256 bearer tokens and extract their authenticated subject."""

    def __init__(
        self,
        *,
        secret: str | None | object = _UNSET,
        issuer: str | None | object = _UNSET,
        audience: str | None | object = _UNSET,
    ) -> None:
        self.secret = (
            settings.auth_jwt_secret
            if secret is _UNSET
            else secret
        )
        self.issuer = (
            settings.auth_jwt_issuer
            if issuer is _UNSET
            else issuer
        )
        self.audience = (
            settings.auth_jwt_audience
            if audience is _UNSET
            else audience
        )

    def authenticate(
        self,
        token: str,
    ) -> AuthenticatedIdentity:
        """Verify a JWT and return its authenticated identity."""

        if not self.secret:
            raise AuthenticationError(
                "JWT authentication is not configured."
            )

        decode_options: dict[str, Any] = {
            "require": ["sub", "exp"],
        }

        kwargs: dict[str, Any] = {
            "algorithms": ["HS256"],
            "options": decode_options,
        }

        if self.issuer:
            kwargs["issuer"] = self.issuer

        if self.audience:
            kwargs["audience"] = self.audience

        try:
            payload = jwt.decode(
                token,
                self.secret,
                **kwargs,
            )
        except InvalidTokenError as exc:
            raise AuthenticationError(
                "Invalid authentication token."
            ) from exc

        subject = payload.get("sub")

        if not isinstance(subject, str) or not subject.strip():
            raise AuthenticationError(
                "Authentication token does not contain a valid subject."
            )

        return AuthenticatedIdentity(
            subject=subject.strip(),
        )