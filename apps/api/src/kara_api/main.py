import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kara_api.config import get_settings
from kara_api.db import close_db, init_db
from kara_api.db.connection import get_engine
from kara_api.knowledge.seeding import seed_if_empty
from kara_api.routers import chat_router, documents_router, knowledge_router, tax_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
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

    app.include_router(chat_router, prefix=settings.API_V1_PREFIX)
    app.include_router(tax_router, prefix=settings.API_V1_PREFIX)
    app.include_router(knowledge_router, prefix=settings.API_V1_PREFIX)
    app.include_router(documents_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    return app


app = create_app()
