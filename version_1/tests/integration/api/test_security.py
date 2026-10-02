"""API security hardening tests."""

import httpx
import pytest
from httpx import ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_api_responses_include_security_headers() -> None:
    """API responses should include the baseline security headers."""

    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Content-Security-Policy"] == (
        "default-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    )


@pytest.mark.asyncio
async def test_api_security_headers_are_applied_to_error_responses() -> None:
    """Security headers should also be present on error responses."""

    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Content-Security-Policy"] == (
        "default-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    )