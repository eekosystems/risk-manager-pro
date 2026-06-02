import asyncio
import base64
import uuid
from typing import cast

import structlog
import tiktoken
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentContentFormat
from azure.core.credentials import AzureKeyCredential

from app.core.config import settings
from app.models.document import DocumentStatus
from app.models.notification import NotificationType
from app.repositories.document import DocumentRepository
from app.services.notification import NotificationDispatcher
from app.services.openai_client import AzureOpenAIClient
from app.services.parser_sandbox import (
    extract_text_local,
    render_pdf_pages,
    run_sandboxed,
)
from app.services.search_indexer import SearchIndexer
from app.services.storage import BlobStorageService

logger = structlog.get_logger(__name__)


class DocumentProcessor:
    def __init__(
        self,
        storage: BlobStorageService,
        openai_client: AzureOpenAIClient,
        indexer: SearchIndexer,
        repo: DocumentRepository,
    ) -> None:
        self._storage = storage
        self._openai = openai_client
        self._indexer = indexer
        self._repo = repo

    @staticmethod
    def _extract_text_ocr(data: bytes) -> str:
        """Use Azure AI Document Intelligence to OCR a scanned PDF."""
        if not settings.azure_doc_intelligence_endpoint:
            raise ValueError(
                "No text extracted and Azure Document Intelligence is not configured for OCR"
            )

        client = DocumentIntelligenceClient(
            endpoint=settings.azure_doc_intelligence_endpoint,
            credential=AzureKeyCredential(settings.azure_doc_intelligence_key),
        )

        poller = client.begin_analyze_document(
            "prebuilt-read",
            AnalyzeDocumentRequest(bytes_source=data),
            output_content_format=DocumentContentFormat.MARKDOWN,
        )
        result = poller.result()
        return result.content or ""

    async def _describe_pdf_pages(self, data: bytes) -> str:
        """Render PDF pages to images and describe visual content via GPT-4o vision."""
        # L-8: render untrusted PDF bytes in a resource-capped subprocess.
        page_images = cast(
            "list[bytes]",
            await asyncio.to_thread(run_sandboxed, render_pdf_pages, data),
        )
        if not page_images:
            return ""

        prompt = (
            "Describe all visual elements on this page: images, photos, diagrams, charts, "
            "maps, logos, tables, and any other non-text content. Be specific about what "
            "you see (e.g., aircraft type, airport layout features, risk matrix values). "
            "If there are no visual elements beyond plain text, respond with NONE."
        )

        descriptions: list[str] = []
        for i, img_bytes in enumerate(page_images, 1):
            try:
                img_b64 = base64.b64encode(img_bytes).decode("ascii")
                description = await self._openai.describe_image(img_b64, prompt)
                if description.strip().upper() != "NONE":
                    descriptions.append(f"[Page {i} visual content]: {description}")
            except Exception:
                logger.warning("page_vision_failed", page=i, exc_info=True)
                continue

        return "\n\n".join(descriptions)

    @staticmethod
    def _chunk_text(text: str) -> list[str]:
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        chunks: list[str] = []

        start = 0
        while start < len(tokens):
            end = start + settings.chunk_size_tokens
            chunk_tokens = tokens[start:end]
            chunk_text = encoding.decode(chunk_tokens)
            chunks.append(chunk_text)
            start = end - settings.chunk_overlap_tokens

        return chunks

    @staticmethod
    async def _extract_text_in_thread(data: bytes, content_type: str) -> str:
        # L-8: parse untrusted bytes in a resource-capped subprocess.
        text = cast(
            "str",
            await asyncio.to_thread(run_sandboxed, extract_text_local, data, content_type),
        )
        if content_type == "application/pdf" and not text.strip():
            logger.info("pdf_no_text_layer_falling_back_to_ocr")
            # OCR is a network call to Azure Document Intelligence — credentials,
            # no untrusted local parsing — so it runs in-process, not sandboxed.
            text = await asyncio.to_thread(DocumentProcessor._extract_text_ocr, data)
        return text

    @staticmethod
    async def _chunk_text_in_thread(text: str) -> list[str]:
        return await asyncio.to_thread(DocumentProcessor._chunk_text, text)

    async def process(self, document_id: uuid.UUID) -> None:
        await self._repo.update_status(document_id, DocumentStatus.PROCESSING)

        try:
            document = await self._repo.get_by_id_system(document_id)
            if not document:
                logger.error("document_not_found", document_id=str(document_id))
                return

            data = await self._storage.download(document.blob_path)
            text = await DocumentProcessor._extract_text_in_thread(data, document.content_type)

            # For PDFs, analyze pages with GPT-4o vision to capture images/diagrams
            if document.content_type == "application/pdf":
                try:
                    image_descriptions = await self._describe_pdf_pages(data)
                    if image_descriptions:
                        text = text + "\n\n" + image_descriptions
                        logger.info(
                            "vision_descriptions_added",
                            document_id=str(document_id),
                        )
                except Exception:
                    logger.warning(
                        "vision_analysis_failed_continuing",
                        document_id=str(document_id),
                        exc_info=True,
                    )

            if not text.strip():
                await self._repo.update_status(
                    document_id, DocumentStatus.FAILED, error_message="No text extracted"
                )
                return

            chunks = await DocumentProcessor._chunk_text_in_thread(text)
            logger.info(
                "document_chunked",
                document_id=str(document_id),
                chunk_count=len(chunks),
            )

            embeddings: list[list[float]] = []
            batch_size = settings.embedding_batch_size
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i : i + batch_size]
                batch_embeddings = await self._openai.embed_batch(batch)
                embeddings.extend(batch_embeddings)

            await self._indexer.index_chunks(
                document_id=document_id,
                organization_id=document.organization_id,
                source=document.filename,
                chunks=chunks,
                embeddings=embeddings,
                source_type=document.source_type.value,
            )

            await self._repo.update_status(
                document_id, DocumentStatus.INDEXED, chunk_count=len(chunks)
            )
            logger.info(
                "document_processed",
                document_id=str(document_id),
                chunks_indexed=len(chunks),
            )

            uploader = await self._repo.get_uploader(document)
            if uploader is not None:
                NotificationDispatcher().dispatch(
                    organization_id=document.organization_id,
                    triggered_by=uploader,
                    notification_type=NotificationType.DOCUMENT_INDEXED,
                    title=f"Document indexed: {document.filename[:100]}",
                    body=f"{len(chunks)} chunks indexed. Source: {document.source_type.value}",
                    resource_type="document",
                    resource_id=str(document.id),
                )

        except Exception as e:
            logger.error(
                "document_processing_failed",
                document_id=str(document_id),
                error=str(e),
                exc_info=True,
            )
            await self._repo.update_status(
                document_id,
                DocumentStatus.FAILED,
                error_message="Document processing failed. See server logs for details.",
            )
