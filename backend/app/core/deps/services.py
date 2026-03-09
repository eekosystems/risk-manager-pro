"""DI providers that pull service singletons from the ServiceRegistry."""

from fastapi import Request

from app.services.microsoft_graph import MicrosoftGraphService
from app.services.openai_client import AzureOpenAIClient
from app.services.rag import RAGService
from app.services.search_indexer import SearchIndexer
from app.services.storage import BlobStorageService


def get_openai_client(request: Request) -> AzureOpenAIClient:
    return request.app.state.services.openai_client


def get_rag_service(request: Request) -> RAGService:
    return request.app.state.services.rag_service


def get_storage_service(request: Request) -> BlobStorageService:
    return request.app.state.services.storage_service


def get_search_indexer(request: Request) -> SearchIndexer:
    return request.app.state.services.search_indexer


def get_graph_service(request: Request) -> MicrosoftGraphService:
    return request.app.state.services.graph_service
