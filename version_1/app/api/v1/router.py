"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.query import router as query_router
from app.api.v1.search import router as search_router
from app.api.v1.daily import router as daily_router


api_router = APIRouter()


api_router.include_router(
    health_router,
    prefix="/api/v1",
)

api_router.include_router(
    documents_router,
    prefix="/api/v1",
)

api_router.include_router(
    search_router,
    prefix="/api/v1",
)

api_router.include_router(
    query_router,
    prefix="/api/v1",
)

api_router.include_router(
    daily_router,
    prefix="/api/v1",
)