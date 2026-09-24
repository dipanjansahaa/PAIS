"""Unit tests for PAIS liveness and readiness endpoints."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.api.v1.health import router


def create_test_app(db: AsyncSession) -> FastAPI:
    """Create an isolated FastAPI app with an overridden DB dependency."""

    app = FastAPI()
    app.include_router(router)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return app


async def request(app: FastAPI, path: str):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


async def test_health_returns_ok_without_database_access() -> None:
    db = AsyncMock(spec=AsyncSession)
    app = create_test_app(db)

    response = await request(app, "/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    db.execute.assert_not_awaited()


async def test_ready_returns_ready_when_database_is_reachable() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = AsyncMock()
    app = create_test_app(db)

    response = await request(app, "/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}
    db.execute.assert_awaited_once()


async def test_ready_returns_503_when_database_is_unavailable() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = OperationalError(
        statement="SELECT 1",
        params=None,
        orig=Exception("database unavailable"),
    )
    app = create_test_app(db)

    response = await request(app, "/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "unavailable",
    }
    db.execute.assert_awaited_once()
