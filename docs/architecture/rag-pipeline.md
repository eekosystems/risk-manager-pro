# RAG Pipeline

Risk Manager Pro answers safety questions using **Retrieval-Augmented Generation (RAG)** over indexed
aviation safety documentation. This document traces both halves of the pipeline: **ingestion**
(document → searchable chunks) and **query** (question → retrieved context → cited answer).

All AI calls go through **Azure OpenAI** (never OpenAI directly). All vector/keyword retrieval goes
through **Azure AI Search** (never a local vector DB).

## 1. Ingestion: document → index

Entry points: file upload (`POST /documents/upload`) and the SharePoint crawler. Processing runs in the
background so uploads return immediately; document `status` moves `UPLOADED → PROCESSING → INDEXED`
(or `FAILED`).

```
Upload (streamed in 1 MB chunks to Blob Storage)
   │
   ▼
document_processor.py
   │
   ├─ 1. Text extraction (SANDBOXED)
   │      run_sandboxed(...) → child process, RLIMIT_AS 2 GiB, RLIMIT_CPU 120s
   │      Parsers: pypdf, python-docx, openpyxl, python-pptx, plain text/CSV
   │      (parser_sandbox.py)
   │
   ├─ 2. OCR fallback (in-process, trusted)
   │      If a PDF has no text layer → Azure Document Intelligence
   │
   ├─ 3. Vision analysis
   │      Render PDF pages to images (PyMuPDF, sandboxed) → GPT-4o vision
   │      extracts charts/diagrams; descriptions appended to text
   │
   ├─ 4. Chunking
   │      tiktoken cl100k_base; sliding window
   │      chunk_size_tokens (default 500), overlap chunk_overlap_tokens (default 50)
   │
   ├─ 5. Embedding
   │      text-embedding-3-small → 1536-dim vectors, batched (default 100)
   │
   └─ 6. Index to Azure AI Search
          Batched upload (default 100); each chunk carries tenant_id = organization_id
```

**Why the sandbox matters:** document parsers operate on untrusted file content and have historically
been a source of memory-exhaustion and parser exploits. `parser_sandbox.py` runs extraction in a
resource-capped subprocess (address space and CPU limited), so a malicious or malformed file cannot take
down the API. OCR and vision steps call trusted Azure services and run in-process.

**Deduplication:** each document stores a SHA-256 `content_hash`; re-uploads of identical content can be
detected. Reindexing (`POST /documents/{id}/reindex`) clears the document's existing chunks before
reprocessing.

## 2. Azure AI Search index schema

Index name: `rmp-documents` (configurable via `AZURE_SEARCH_INDEX_NAME`). Defined in
`backend/app/services/search_schema.py`.

| Field | Type | Searchable | Filterable | Purpose |
|-------|------|-----------|-----------|---------|
| `chunk_id` | String (key) | – | yes | `{document_id}_{chunk_index}` |
| `document_id` | String | – | yes | Parent document |
| `tenant_id` | String | – | yes | **Organization scope** |
| `source` | String | yes | yes | Filename (facetable) |
| `source_type` | String | – | yes | client / faa / icao / … |
| `section` | String | yes | yes | Section label |
| `content` | String | yes | – | Chunk text (en.microsoft analyzer) |
| `content_vector` | Collection(Single) | vector | – | 1536-dim embedding |
| `page_number` | Int32 | – | yes | PDF page reference |
| `chunk_index` | Int32 | – | yes | Sequence |
| `created_at` | DateTimeOffset | – | yes | Index timestamp |

**Vector config:** HNSW (m=4, ef_construction=400, ef_search=500), cosine similarity.

## 3. Query: question → cited answer

Entry point: `POST /chat` (and `POST /chat/stream` for SSE). Orchestrated by
`services/chat.py` calling `services/rag.py`.

```
User message (+ optional referenced filenames, recent upload IDs)
   │
   ▼
routing.py        Determine function type (general/phl/sra/system/risk_register)
   │              Regex rules first, small-model classification fallback.
   │              Killswitch: CHAT_SMART_ROUTING (default on)
   ▼
rag.py: hybrid_search()
   │   1. Validate organization_id (must be a valid UUID)
   │   2. Cap top_k at server-side _MAX_TOP_K = 20
   │   3. Embed the query (text-embedding-3-small)
   │   4. Build the OData filter:
   │         base:     tenant_id eq '<org_id>'              ← tenant isolation
   │         optional: and (source eq '..' or source eq '..')  ← validated, quote-escaped
   │   5. Execute hybrid search: keyword (search_text) + vector (content_vector kNN)
   │   6. Map hits → SearchResult(content, source, source_type, section, score, chunk_id)
   ▼
prompts.py        Build the system prompt for the function type + retrieved chunks as
   │              untrusted "context".
   ▼
openai_client.py  GPT-4o chat completion (streamed or full)
   │
   ▼
Response: assistant message + citations (doc_id, chunk_idx, snippet)
          persisted on the Message row; rendered in the UI with source links
```

### Security controls in the query path

- **Tenant isolation** — the OData filter always pins `tenant_id` to the caller's organization. There
  is no cross-tenant retrieval path.
- **`top_k` ceiling** — requested `top_k` is hard-capped at 20 server-side to bound cost and prevent
  context-window abuse.
- **Source-filter injection defense** — when a user references specific document names, those names are
  validated (max length, no control characters) and single-quotes are escaped before being placed in the
  OData filter.
- **Prompt-injection posture** — retrieved chunks are treated as untrusted context, not instructions.
- **Grounding requirement** — per the engineering standards, the assistant must cite sources and must
  not fabricate safety data; if the retrieved context does not support an answer, it should say so.

## 4. Function types and prompts

The chat experience adapts to five **function types**, each with its own system prompt
(`services/prompts.py`):

| Function | Purpose |
|----------|---------|
| `general` | Freeform safety Q&A (fallback) |
| `phl` | Preliminary Hazard List — identify hazards |
| `sra` | Safety Risk Assessment — score hazards (severity × likelihood) |
| `system` | System analysis — decompose a system |
| `risk_register` | Structured hazard entry into the airport risk register (tool-calling) |

Smart routing (`routing.py`) classifies an incoming message and may switch the function type; the
response reports the chosen `routed_function_type`, and the UI surfaces a toast when routing changes.

## 5. Streaming

`POST /chat/stream` returns Server-Sent Events. The frontend consumes them with the fetch API as an
async generator: events are `data: `-prefixed JSON lines delimited by a blank line, carrying content
deltas, the conversation ID, and citations as they arrive. See
[frontend-guide.md](../frontend/frontend-guide.md).

## 6. Configuration knobs

Set in `backend/app/core/config.py` (environment variables):

| Variable | Default | Effect |
|----------|---------|--------|
| `AZURE_OPENAI_DEPLOYMENT_NAME` | `gpt-4o` | Chat/vision model deployment |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | `text-embedding-3-small` | Embedding model |
| `AZURE_OPENAI_API_VERSION` | `2024-10-21` | API version |
| `AZURE_SEARCH_INDEX_NAME` | `rmp-documents` | Search index |
| `CHUNK_SIZE_TOKENS` | `500` | Chunk size |
| `CHUNK_OVERLAP_TOKENS` | `50` | Chunk overlap |
| `EMBEDDING_BATCH_SIZE` | `100` | Embedding batch size |
| `SEARCH_INDEX_BATCH_SIZE` | `100` | Index upload batch size |
| `PROCESSING_CONCURRENCY` | `5` | Concurrent document-processing tasks |
| `CHAT_SMART_ROUTING` | `true` | Enable function-type auto-routing |
| `AZURE_DOC_INTELLIGENCE_ENDPOINT` / `_KEY` | – | OCR fallback service |

Per-organization overrides for RAG behavior, model preferences, and prompts are stored in
`organization_settings` (categories `rag`, `model`, `prompts`, `qaqc`) and editable by org admins via
`PUT /settings/*`.
</content>
