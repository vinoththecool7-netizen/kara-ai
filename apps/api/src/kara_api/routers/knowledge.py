"""Knowledge base search endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from kara_api.db.connection import get_db_session
from kara_api.knowledge.embeddings import get_embedding_provider
from kara_api.knowledge.search import SearchResult, hybrid_search
from kara_api.runtime_config import get_effective_settings

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    k: int = Field(default=5, ge=1, le=20)


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str


@router.post("/search", response_model=SearchResponse)
async def search_knowledge_base(
    request: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
) -> SearchResponse:
    """Search the tax knowledge base using hybrid search."""
    settings = await get_effective_settings()
    provider = get_embedding_provider(settings)
    results = await hybrid_search(
        query=request.query,
        k=request.k,
        session=session,
        provider=provider,
    )
    return SearchResponse(results=results, query=request.query)
