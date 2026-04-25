from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_organization, require_any_member
from app.models.organization import Organization
from app.models.user import User
from app.repositories.search import SearchRepository
from app.schemas.common import DataResponse, MetaResponse
from app.schemas.search import ConversationHit, DocumentHit, SearchResults

router = APIRouter(prefix="/search", tags=["search"])

_SNIPPET_RADIUS = 80
_MAX_SNIPPET_LEN = 200


def _build_snippet(content: str, query: str) -> str:
    """Return a short excerpt around the first case-insensitive match of query."""
    if not content:
        return ""
    lower = content.lower()
    idx = lower.find(query.lower())
    if idx < 0:
        return content[:_MAX_SNIPPET_LEN].strip()
    start = max(0, idx - _SNIPPET_RADIUS)
    end = min(len(content), idx + len(query) + _SNIPPET_RADIUS)
    snippet = content[start:end].strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(content) else ""
    return f"{prefix}{snippet}{suffix}"


@router.get("", response_model=DataResponse[SearchResults])
async def search(
    q: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(10, ge=1, le=25),
    current_user: User = Depends(require_any_member),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> DataResponse[SearchResults]:
    """Search conversations (by message content) and documents (by filename) for the org."""
    repo = SearchRepository(db)
    convo_rows = await repo.search_conversations(organization.id, q, limit)
    document_rows = await repo.search_documents(organization.id, q, limit)

    conversations = [
        ConversationHit(
            id=conv.id,
            title=conv.title,
            function_type=conv.function_type.value,
            snippet=_build_snippet(msg.content, q),
            matched_message_id=msg.id,
            updated_at=conv.updated_at,
        )
        for conv, msg in convo_rows
    ]
    documents = [
        DocumentHit(
            id=doc.id,
            filename=doc.filename,
            source_type=doc.source_type.value,
            status=doc.status.value,
        )
        for doc in document_rows
    ]

    return DataResponse(
        data=SearchResults(conversations=conversations, documents=documents),
        meta=MetaResponse(request_id=""),
    )
