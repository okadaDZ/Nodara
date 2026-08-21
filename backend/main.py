from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.router import router as api_router
from core.bootstrap import bootstrap
from core.settings import settings
from libs.database.session import init_db
from libs.langchain.chains.chain_store import get_chain_store
from libs.langchain.langfuse_client import flush as flush_langfuse, verify_connection
from libs.scheduler.service import scheduler_service

# Run bootstrap logging setup
bootstrap()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifespan context."""
    verify_connection()
    logger.info("Initializing SQLite database tables...")
    init_db()
    logger.info("Database initialized successfully.")
    chain_store = get_chain_store()
    logger.info("Diagram workflow pipeline initialized with %s.", type(chain_store.provider).__name__)
    await scheduler_service.start()
    try:
        yield
    finally:
        await scheduler_service.stop()
        flush_langfuse()
        logger.info("Application shutdown complete.")


def error_response(
    message: str,
    err_type: str = "invalid_request_error",
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> JSONResponse:
    """Standardized error envelope for clients."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "type": err_type,
                "code": status_code,
            }
        },
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.project_name,
        description="Nodara workflow builder API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Configure CORS for React Native / Expo development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def root_health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):
        return error_response(
            message=str(exc.detail),
            err_type="http_error",
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return error_response(
            message="An unexpected server error occurred. Please try again.",
            err_type="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    app.include_router(api_router)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
