"""PAIS FastAPI application entry point."""

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings


def create_app() -> FastAPI:
    """Create and configure the PAIS FastAPI application."""

    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
    )
    application.include_router(api_router)
    return application


app = create_app()
