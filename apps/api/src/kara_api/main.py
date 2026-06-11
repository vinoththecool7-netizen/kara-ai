import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from kara_api.config import get_settings
from kara_api.db import close_db, init_db
from kara_api.db.connection import get_engine
from kara_api.knowledge.seeding import seed_if_empty
from kara_api.middleware import (
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    setup_logging,
)
from kara_api.routers import chat_router, documents_router, knowledge_router, tax_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    setup_logging(logging.DEBUG if settings.DEBUG else logging.INFO)
    await init_db(settings.DATABASE_URL, echo=settings.DEBUG)
    try:
        await seed_if_empty(get_engine(), settings)
    except Exception:
        # The app is still useful without the knowledge base (tax computation,
        # chat); log and continue rather than failing startup.
        logger.exception("Knowledge base seeding failed; continuing without it")
    yield
    # Shutdown
    await close_db()


async def _database_reachable() -> bool:
    """True when the engine is initialized and answers a SELECT 1 quickly."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=2.0)
        return True
    except Exception:
        return False


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Kara API",
        description="AI Tax Advisor for India",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Pure-ASGI middleware — safe for streaming SSE responses
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request, exc):
        # Full details go to the logs (with request id); clients get a
        # generic message — never internals.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(chat_router, prefix=settings.API_V1_PREFIX)
    app.include_router(tax_router, prefix=settings.API_V1_PREFIX)
    app.include_router(knowledge_router, prefix=settings.API_V1_PREFIX)
    app.include_router(documents_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health")
    async def health_check():
        if await _database_reachable():
            return {"status": "ok", "database": "ok"}
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "unavailable"},
        )

    return app


app = create_app()
