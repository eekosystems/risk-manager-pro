import asyncio
import io
import uuid

import structlog
import tiktoken

from app.models.document import DocumentStatus
from app.repositories.document import DocumentRepository
from app.services.openai_client import AzureOpenAIClient
from app.services.search_indexer import SearchIndexer
from app.services.storage import BlobStorageService

logger = structlog.get_logger(__name__)

CHUNK_SIZE_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 50


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
    def _extract_text_pdf(data: bytes) -> str:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)

    @staticmethod
    def _extract_text_docx(data: bytes) -> str:
        from docx import Document as DocxDocument

        doc = DocxDocument(io.BytesIO(data))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())

    @staticmethod
    def _extract_text_plain(data: bytes) -> str:
        return data.decode("utf-8", errors="replace")

    @staticmethod
    def _extract_text(data: bytes, content_type: str) -> str:
        if content_type == "application/pdf":
            return DocumentProcessor._extract_text_pdf(data)
        elif content_type == (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            return DocumentProcessor._extract_text_docx(data)
        elif content_type == "text/plain":
            return DocumentProcessor._extract_text_plain(data)
        else:
            raise ValueError(f"Unsupported content type: {content_type}")

    @staticmethod
    def _chunk_text(text: str) -> list[str]:
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        chunks: list[str] = []

        start = 0
        while start < len(tokens):
            end = start + CHUNK_SIZE_TOKENS
            chunk_tokens = tokens[start:end]
            chunk_text = encoding.decode(chunk_tokens)
            chunks.append(chunk_text)
            start = end - CHUNK_OVERLAP_TOKENS

        return chunks

    @staticmethod
    async def _extract_text_in_thread(data: bytes, content_type: str) -> str:
        return await asyncio.to_thread(DocumentProcessor._extract_text, data, content_type)

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
            batch_size = 16
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
            )

            await self._repo.update_status(
                document_id, DocumentStatus.INDEXED, chunk_count=len(chunks)
            )
            logger.info(
                "document_processed",
                document_id=str(document_id),
                chunks_indexed=len(chunks),
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
