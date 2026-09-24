"""Integration tests for the containerized PostgreSQL readiness path.

Run these tests only when PostgreSQL is available at DATABASE_URL.
"""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.integration
def test_ready_with_real_database() -> None:
    """Verify /ready against a real PostgreSQL instance."""

    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run database integration tests.")

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "available",
    }
