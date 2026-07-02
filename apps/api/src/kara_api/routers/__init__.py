from kara_api.routers.chat import router as chat_router
from kara_api.routers.documents import router as documents_router
from kara_api.routers.knowledge import router as knowledge_router
from kara_api.routers.setup import router as setup_router
from kara_api.routers.tax import router as tax_router

__all__ = [
    "chat_router",
    "documents_router",
    "knowledge_router",
    "setup_router",
    "tax_router",
]
