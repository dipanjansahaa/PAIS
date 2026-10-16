"""PAIS FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.responses import Response

from app.api.v1.router import api_router
from app.core.config import settings


def create_app() -> FastAPI:
    """Create and configure the PAIS FastAPI application."""

    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
    )

    @application.middleware("http")
    async def add_security_headers(
        request: Request,
        call_next,
    ) -> Response:
        """Add baseline security headers to every HTTP response."""

        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'"
        )

        return response

    application.include_router(api_router)

    return application


app = create_app()