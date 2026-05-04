
# PolyMath
## `extractor.py` — PDF Ingestion Module
This file is responsible for pulling raw content out of PDF files. It's the entry point for any PDF that lands in your system, and it uses **two libraries in tandem** — `pdfplumber` and `PyMuPDF (fitz)` — each covering the other's weak spots.
---
### The Two-Library Strategy
| Library | Strength | Used for |
|---|---|---|
| `fitz` (PyMuPDF) | Fast, reads embedded PDF metadata reliably | Metadata extraction, fallback text |
| `pdfplumber` | Better at complex layouts (columns, tables) | Page text extraction, page count, preview |
Neither library is perfect for everything, so the code uses both strategically.
---
### `extract_metadata(pdf_path)` → `dict`
Builds a metadata dict with four keys: `title`, `author`, `page_count`, and `preview`.
**Flow:**
1. **fitz opens the PDF first** — reads the embedded metadata header (like the "Properties" of a PDF file). This gives you `title` and `author` cheaply without reading page content.
2. **pdfplumber opens the same file** — it counts pages and reads the first `CATALOG_PREVIEW_PAGES` pages (a config constant) to build a `preview` snippet, capped at 500 characters.
3. **Fallback title** — if the embedded metadata had no title (common with scanned docs or poorly-exported PDFs), it calls `_extract_title_from_text()` to guess the title from the first line of the text.
---
### `extract_pages(pdf_path)` → `list[dict]`
Returns a list like:
```python
[
  {"page_number": 1, "text": "Introduction ..."},
  {"page_number": 2, "text": "Chapter 1 ..."},
  ...
]
```
**Flow — for each page:**
1. **pdfplumber tries first** — it's better at handling multi-column academic papers, tables, etc.
2. **fitz steps in as fallback** — if pdfplumber returns empty text (e.g. a scanned image page or a page where plumber can't parse the layout), fitz attempts the same page with its own renderer.
Note that both `pdfplumber` and the `fitz` doc are **open simultaneously** inside the `with` block — this is intentional to avoid repeatedly reopening the file on every page fallback.
Page numbers are **1-indexed** (human-friendly) rather than 0-indexed, since they'll likely be shown in a UI or stored in a catalog.
---
### Helper Functions
**`_clean(value)`**
Sanitizes raw metadata strings. PDF metadata often contains null bytes (`\x00`) and irregular whitespace — this strips both. It's called on every title/author value before storing.
**`_extract_title_from_text(text)`**
A heuristic fallback. It scans lines top-to-bottom and returns the first line that's longer than 4 characters (skipping page numbers, single letters, etc.), capped at 120 chars to avoid accidentally grabbing a full paragraph as a "title".
---
### Key Design Decisions
- **Dual-library redundancy** is the core pattern — neither library is trusted exclusively, which makes extraction resilient across different PDF types (native, scanned, table-heavy, etc.)
- **`CATALOG_PREVIEW_PAGES` from config** makes the preview depth configurable without touching this file
- **Both extractors are stateless** — pure functions in, data out — making them easy to test or swap out
- **fitz doc is opened inside the pdfplumber `with` block** in `extract_pages` — a deliberate choice to keep both handles alive for the per-page fallback without re-opening on every miss

Great questions — both are simpler than they sound.
---
### "In Tandem"
Tandem just means **working together at the same time, each doing a different job** — like two people on a tandem bicycle, both pedaling.
In this context it means: instead of picking *one* library to handle everything, the code uses *both* — `pdfplumber` does some tasks, `fitz` does others, and they cover each other's gaps. Neither is used in isolation.
---
### "Embedded Metadata" — not embeddings
No, this has **nothing to do with vector embeddings or AI**. It's a much simpler concept.
Every PDF file has two parts:
**1. The metadata header** — a small block of information *about* the file, baked into the PDF itself when it was created or exported. Things like:
- Title
- Author
- Creation date
- Software that made it (e.g. "Microsoft Word")
**2. The actual content** — pages, text, images, etc.
"Embedded" here just means this metadata is **stored inside the PDF file itself**, not in a separate database or filename. It's like the ID card stitched into the file.
---
### A simple analogy
Think of a PDF like a book:
- The **embedded metadata** = the copyright page at the front (author, publisher, year)
- The **page content** = the actual chapters
`fitz` reads the copyright page (fast, structured).
`pdfplumber` reads the chapters (slower, but handles complex layouts better).
---
So — completely normal PDFs, no AI involved at this stage. The "embeddings" (vector/semantic kind) would only come *later* in a pipeline, after this raw text has been extracted.
Really good observation. The reason is the **type hint is a lie** (or rather, a simplification).
---
### The function signature says:
```python
def extract_metadata(pdf_path: str) -> dict:
```
This *suggests* a string is coming in. But in Python, **type hints are not enforced** — they're just documentation. Nothing stops someone from calling this function with a different type.
---
### In practice, `pdf_path` could arrive as:
```python
extract_metadata("documents/file.pdf")        # str — plain string
extract_metadata(Path("documents/file.pdf"))  # Path object — from pathlib
extract_metadata(some_path_variable)          # unknown — depends on caller
```
`pathlib.Path` objects are extremely common in Python projects for handling file paths. They are **not** strings, but they look similar.
---
### So `path = str(pdf_path)` is a **defensive conversion**
It says: *"whatever type came in — string, Path object, or anything else that has a string representation — convert it to a plain string before passing it to fitz/pdfplumber."*
Both `fitz.open()` and `pdfplumber.open()` expect a plain string path, so this one line makes the function safe regardless of what the caller passes in.
---
### In short:
| Scenario | Without `str()` | With `str()` |
|---|---|---|
| Caller passes `str` | Works fine | Works fine |
| Caller passes `Path` | Might break | Works fine |
| Caller passes something else | Breaks | Safely converts |
It's a small defensive habit — costs nothing, prevents subtle bugs.
Great question. It's using Python's **truthy/falsy** concept — there's no explicit `== ""` check written, but Python does it automatically.
In Python, an empty string `""` is automatically treated as `False`, and any non-empty string is treated as `True`.
```python
bool("")          # → False
bool("   ")       # → False  (wait — only spaces)
bool("hello")     # → True
```
So when you write:
```python
if not text.strip():
```
Python is silently doing:
```python
if not bool(text.strip()):
```
Which means:
- If `text.strip()` gives `""` → `bool("")` = `False` → `not False` = `True` → **skip**
- If `text.strip()` gives `"hello"` → `bool("hello")` = `True` → `not True` = `False` → **don't skip**
So `if not text.strip()` is just a shorter, more Pythonic way of writing `if text.strip() == "":`. Both do the exact same thing — Python developers just prefer the shorter form.




## The `composite` Score
It's a **single weighted average** that combines the individual RAGAS metrics into one overall quality score.
### How it's calculated
**Without `context_recall`:**
```python
composite = (faithfulness × 0.40) +
            (answer_relevance × 0.35) +
            (context_precision × 0.25)
```
**With `context_recall`:**
```python
composite = (faithfulness × 0.40) +      # → 0.35
            (answer_relevance × 0.35) +   # → 0.30
            (context_precision × 0.25) +  # → 0.20
            (context_recall × 0.15)
```
The weights **redistribute** when `context_recall` is available.
### Why weighted and not a simple average?
The weights reflect **how much each metric matters** for RAG quality:
| Metric | Weight | Why |
|---|---|---|
| `faithfulness` | highest (0.35–0.40) | Did the answer stick to the retrieved context? Hallucination prevention — most critical |
| `answer_relevance` | second (0.30–0.35) | Did the answer actually address the question? |
| `context_precision` | third (0.20–0.25) | Was the retrieved context focused and not noisy? |
| `context_recall` | lowest (0.15) | Did retrieval capture all needed info? Optional because ground truth is needed to compute it |
### The end result
Instead of juggling 3–4 numbers, you get **one score between 0 and 1** to quickly judge overall RAG pipeline quality — useful for comparing runs, tuning, or setting a pass/fail threshold.
## The Two `@property` Decorators
`@property` turns a method into an **attribute** — you access it without calling it (no parentheses).
```python
chunk.display_text   # ✅ property
chunk.display_text() # ❌ would error
```
---
## `display_text`
```python
@property
def display_text(self) -> str:
    return self.metadata.contextualized_text or self.metadata.text
```
This is a **fallback pattern**. It returns whichever text is available:
```
contextualized_text exists? → use it
contextualized_text is None/empty? → fall back to plain text
```
`contextualized_text` is likely an enriched version of the chunk (e.g. with surrounding context added), while `text` is the raw chunk. You always want the best version available.
---
## `citation_label`
```python
@property
def citation_label(self) -> str:
    loc = f"p.{self.metadata.page_number}"
    if self.metadata.chapter_title:
        loc = f"{self.metadata.chapter_title}, {loc}"
    return f"[{self.metadata.doc_title} — {loc}]"
```
Builds a **human-readable citation string** in two steps:
**Step 1** — start with just the page:
```
loc = "p.42"
```
**Step 2** — prepend chapter title if it exists:
```
loc = "Introduction, p.42"
```
**Final output:**
```
[My Book Title — Introduction, p.42]
```
This is the kind of string you'd show in a RAG response like:
> *"According to the document... [My Book Title — Introduction, p.42]"*
---
### Why `@property` instead of regular methods?
These are **derived read-only values** computed from existing data — not actions. Using `@property` makes them feel like natural attributes of the object, keeping the interface clean.
EXACTLY. That's the right question. Let me think through what's genuinely new in Polymath vs QueryMind.
---
## What QueryMind already had
- Chunks with metadata
- FAISS retrieval
- Query → response flow
- Basic eval with RAGAS
- FastAPI
---
## What Polymath introduces that is genuinely new
**1. Per-document isolation**
QueryMind had one global FAISS index. Polymath has one index per document. So we need models that represent "which document does this chunk belong to" and "retrieve from this specific document's index only."
**2. The Catalog**
A JSON registry of every uploaded document — title, type, chapters, page ranges, preview text, domain tags. The agent reads this at query time to decide which documents are even relevant before touching FAISS. QueryMind had nothing like this.
**3. Document Type Detection**
Book vs research paper. Different structure, different chunking behavior, different metadata extracted. QueryMind treated every PDF the same.
**4. Dual Mode — Q&A vs Synthesize**
Synthesize mode is completely new. It means querying multiple documents separately, then running a structured comparison — agreements, contradictions, unique insights. That's a whole new output shape.
**5. Self-eval retry loop**
RAGAS scores below threshold → agent automatically re-retrieves with a refined query and tries again. QueryMind just scored. It didn't act on the score.
**6. Session memory**
Conversation history maintained across turns within a session. QueryMind was stateless.
**7. SSE streaming with node-level events**
Not just streaming tokens — streaming which agent node is currently running so the frontend can show "Selecting documents... Retrieving... Generating..."
---
So the **new models** we need that QueryMind never had are around these 7 things specifically.
Now tell me — which of these 7 do you want to understand more deeply before we start defining the shapes?
Okay. File structure first, then we go one file at a time with explanation alongside code.
---
## Final File Structure
```
polymath/
│
├── core/
│   ├── __init__.py
│   ├── config.py               ✅ DONE
│   ├── models.py               ← NEXT
│   └── document_store.py
│
├── ingestion/
│   ├── __init__.py
│   ├── detector.py
│   ├── parser.py
│   ├── chunker.py
│   ├── embedder.py
│   └── contextualizer.py
│
├── catalog/
│   ├── __init__.py
│   └── manager.py
│
├── retrieval/
│   ├── __init__.py
│   ├── retriever.py
│   ├── hyde.py
│   ├── multi_query.py
│   └── compressor.py
│
├── agents/
│   ├── __init__.py
│   ├── state.py
│   ├── nodes.py
│   ├── graph.py
│   ├── prompts.py
│   └── router.py
│
├── synthesis/
│   ├── __init__.py
│   ├── comparator.py
│   └── summarizer.py
│
├── eval/
│   ├── __init__.py
│   ├── evaluator.py
│   ├── golden_dataset.py
│   └── score_store.py
│
├── api/
│   ├── __init__.py
│   ├── main.py
│   └── routes/
│       ├── upload.py
│       ├── query.py
│       ├── documents.py
│       └── scores.py
│
├── storage/
│   ├── catalog.json
│   ├── indexes/
│   └── scores/
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── components/
│       │   ├── ChatWindow.tsx
│       │   ├── MessageBubble.tsx
│       │   ├── ModeToggle.tsx
│       │   ├── Sidebar.tsx
│       │   ├── UploadZone.tsx
│       │   └── ScorePanel.tsx
│       ├── hooks/
│       │   ├── useChat.ts
│       │   └── useDocuments.ts
│       ├── store/
│       │   └── chatStore.ts
│       ├── types/
│       │   └── index.ts
│       └── lib/
│           └── api.ts
│
├── tests/
│   ├── test_ingestion.py
│   ├── test_retrieval.py
│   └── test_agents.py
│
├── .env
├── .env.example
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```
---
Now `core/models.py`.
## What this file does
Every piece of data that flows through Polymath needs a defined shape. This file defines those shapes using Pydantic. Think of it as the **data contract** of the entire system.
We have 7 genuinely new things in Polymath. Each needs its own model group:
---
## `core/models.py`
```python
from __future__ import annotations
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
```
**Why these imports?**
- `Enum` — for fixed choices like document type, query mode
- `Pydantic BaseModel` — gives us validation, serialization, autocomplete
- `uuid` — every document, chunk, session gets a unique ID automatically
- `datetime` — timestamps on everything for observability
---
```python
# ─── Enums ────────────────────────────────────────────────
class DocumentType(str, Enum):
    BOOK = "book"
    PAPER = "paper"
    UNKNOWN = "unknown"
class QueryMode(str, Enum):
    QA = "qa"
    SYNTHESIZE = "synthesize"
class RetrievalStrategy(str, Enum):
    STANDARD = "standard"
    HYDE = "hyde"
    MULTI_QUERY = "multi_query"
    HYBRID = "hybrid"
class EvalStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"
```
**Why enums?**
These are fixed choices. If something can only be "book" or "paper", an enum prevents anyone from passing "Book" or "BOOK" or "buk" by accident. `str, Enum` means it serializes to a plain string in JSON automatically.
`RetrievalStrategy` is new — QueryMind always used the same retrieval. Polymath lets the agent choose between standard, HyDE, multi-query, or hybrid depending on the query.
---
```python
# ─── Catalog Models ───────────────────────────────────────
class ChapterEntry(BaseModel):
    title: str
    page_start: int
    page_end: Optional[int] = None
    level: int = Field(default=1)
```
**Why?**
This represents one row in a document's table of contents. `level` distinguishes Chapter → Section → Subsection. QueryMind had none of this — it had no concept of document structure.
---
```python
class DocumentCatalogEntry(BaseModel):
    doc_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    title: str
    doc_type: DocumentType
    total_pages: int
    file_size_bytes: int
    file_hash: str
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
    chapters: list[ChapterEntry] = Field(default_factory=list)
    preview_text: str = ""
    abstract: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    index_path: str = ""
    chunks_path: str = ""
    total_chunks: int = 0
```
**Why?**
This is the catalog entry — one per uploaded document, written to `catalog.json`. The agent reads this at query time to decide which documents to search **before touching FAISS**. `file_hash` enables deduplication — if you upload the same PDF twice, we catch it. `preview_text` is what the agent reads to decide relevance. `index_path` and `chunks_path` tell the retriever exactly where on disk to load this document's FAISS index from.
---
```python
# ─── Chunk Models ─────────────────────────────────────────
class ChunkMetadata(BaseModel):
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    doc_id: str
    doc_title: str
    doc_type: DocumentType
    filename: str
    page_number: int
    chapter_title: Optional[str] = None
    section_title: Optional[str] = None
    text: str
    contextualized_text: Optional[str] = None
    char_count: int = 0
    retrieval_score: float = 0.0
    rerank_score: Optional[float] = None
```
**Why?**
Every chunk knows exactly where it came from — which document, which chapter, which page. `contextualized_text` is new — after chunking, the contextualizer runs an LLM over each chunk and prepends a one-sentence summary of the broader document context. This dramatically improves retrieval quality. QueryMind had raw text only.
---
```python
class RetrievedChunk(BaseModel):
    metadata: ChunkMetadata
    score: float
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.STANDARD
    @property
    def display_text(self) -> str:
        return self.metadata.contextualized_text or self.metadata.text
    @property
    def citation_label(self) -> str:
        loc = f"p.{self.metadata.page_number}"
        if self.metadata.chapter_title:
            loc = f"{self.metadata.chapter_title}, {loc}"
        return f"[{self.metadata.doc_title} — {loc}]"
```
**Why?**
A chunk that came back from retrieval with its score attached. `display_text` automatically uses contextualized text if available. `citation_label` auto-generates the source citation string the frontend displays.
---
```python
# ─── Structured Context ───────────────────────────────────
class DocumentContext(BaseModel):
    doc_id: str
    doc_title: str
    doc_type: DocumentType
    chunks: list[RetrievedChunk]
    @property
    def formatted_text(self) -> str:
        lines = [f"=== SOURCE: {self.doc_title} ({self.doc_type}) ==="]
        for i, chunk in enumerate(self.chunks, 1):
            lines.append(
                f"\n[Chunk {i} | {chunk.citation_label}]\n{chunk.display_text}"
            )
        return "\n".join(lines)
```
**Why?**
This is the core architectural difference from QueryMind. Instead of mashing all retrieved chunks into one blob, each document gets its own `DocumentContext` block with a clear label. The LLM receives a list of these — it always knows which text came from which source. This is what makes synthesis mode possible.
---
```python
# ─── Session Memory ───────────────────────────────────────
class ConversationTurn(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    mode: Optional[QueryMode] = None
    doc_ids_used: list[str] = Field(default_factory=list)
class SessionMemory(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    turns: list[ConversationTurn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    def add_turn(self, role: str, content: str,
                 mode: Optional[QueryMode] = None,
                 doc_ids: Optional[list[str]] = None) -> None:
        self.turns.append(ConversationTurn(
            role=role, content=content,
            mode=mode, doc_ids_used=doc_ids or []
        ))
    def get_history_text(self, max_turns: int = 10) -> str:
        recent = self.turns[-max_turns * 2:]
        lines = []
        for turn in recent:
            prefix = "User" if turn.role == "user" else "Assistant"
            lines.append(f"{prefix}: {turn.content}")
        return "\n".join(lines)
```
**Why?**
QueryMind was stateless — every query was independent. Polymath maintains conversation history per session. `get_history_text` formats the last N turns for injection into prompts so the agent understands follow-up questions.
---
```python
# ─── Eval Models ──────────────────────────────────────────
class RAGASScores(BaseModel):
    faithfulness: float = Field(ge=0.0, le=1.0)
    answer_relevance: float = Field(ge=0.0, le=1.0)
    context_precision: float = Field(ge=0.0, le=1.0)
    context_recall: Optional[float] = None
    composite: float = Field(ge=0.0, le=1.0)
    @classmethod
    def compute_composite(
        cls,
        faithfulness: float,
        answer_relevance: float,
        context_precision: float,
        context_recall: Optional[float] = None
    ) -> "RAGASScores":
        scores = [faithfulness, answer_relevance, context_precision]
        weights = [0.4, 0.35, 0.25]
        if context_recall is not None:
            scores.append(context_recall)
            weights = [0.35, 0.30, 0.20, 0.15]
        composite = sum(s * w for s, w in zip(scores, weights))
        return cls(
            faithfulness=faithfulness,
            answer_relevance=answer_relevance,
            context_precision=context_precision,
            context_recall=context_recall,
            composite=composite
        )
class EvalResult(BaseModel):
    eval_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    query: str
    response: str
    scores: RAGASScores
    status: EvalStatus
    retry_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
```
**Why?**
QueryMind scored responses but never acted on them. Here `EvalResult` carries a `status` — PASSED, FAILED, RETRYING. The agent node reads this and decides whether to re-retrieve. `composite` is a weighted average — faithfulness weighted highest because a hallucinated answer is worse than an irrelevant one.
---
```python
# ─── API Models ───────────────────────────────────────────
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    mode: QueryMode = QueryMode.QA
    session_id: Optional[str] = None
    doc_ids: Optional[list[str]] = None
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    stream: bool = True
class QueryResponse(BaseModel):
    session_id: str
    query: str
    mode: QueryMode
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    eval_scores: Optional[RAGASScores] = None
    docs_used: list[str] = Field(default_factory=list)
    latency_ms: Optional[float] = None
class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    title: str
    doc_type: DocumentType
    total_pages: int
    total_chunks: int
    chapters_found: int
    message: str = "Document processed successfully"
class SSEEvent(BaseModel):
    event: str  # node_start | token | node_done | eval_result | error | done
    data: Any
    session_id: Optional[str] = None
```
**Why SSEEvent?**
This is new. Every server-sent event has a type so the frontend knows what to do with it. `node_start` → show "Retrieving documents...". `token` → stream text character by character. `eval_result` → show RAGAS scores. `done` → close the stream.
---
```python
# ─── Synthesis Models ─────────────────────────────────────
class SynthesisSection(BaseModel):
    heading: str
    content: str
    source_doc_ids: list[str] = Field(default_factory=list)
class SynthesisOutput(BaseModel):
    synthesis_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    docs_synthesized: list[str]
    agreements: list[SynthesisSection] = Field(default_factory=list)
    contradictions: list[SynthesisSection] = Field(default_factory=list)
    unique_insights: list[SynthesisSection] = Field(default_factory=list)
    consolidated_notes: str = ""
    markdown_output: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
```
**Why?**
Synthesis mode doesn't just answer — it structures the output into agreements, contradictions, and unique insights per source. `markdown_output` is the final downloadable string the frontend offers as a file download.
---
That's the complete `core/models.py` with every decision explained.
Tell me when you've written it and we move to `core/document_store.py`.
Great question. Yes — for the **contextualizer** (adding doc-level context to chunks) we can absolutely use a small HuggingFace summarization model instead of burning Groq API calls.
Good candidates:
- `facebook/bart-large-cnn` — best quality, ~1.6GB
- `sshleifer/distilbart-cnn-12-6` — distilled, faster, ~1.2GB
- `google/flan-t5-base` — smallest, ~250MB, CPU friendly
Since you're on CPU during dev, `flan-t5-base` makes the most sense. We'll make it configurable in `config.py` so you can swap later.
We'll handle this properly when we reach `ingestion/contextualizer.py`.
---
Now `core/document_store.py`.
## What this file does
The catalog manager handles the JSON file. But `document_store.py` sits one level above — it's the **single source of truth** for:
- Has this file been uploaded before? (deduplication via SHA256 hash)
- Give me all documents currently in the system
- Delete a document and clean up its index files from disk
- Is a given `doc_id` valid?
Think of it as the database layer — except instead of Postgres, our "database" right now is `catalog.json` plus FAISS files on disk.
**Why separate from catalog manager?**
Catalog manager just reads and writes JSON. Document store has business logic — deduplication, deletion cascades, validation. Separation of concerns.
---
## `core/document_store.py`
```python
import hashlib
import shutil
import logging
from pathlib import Path
from typing import Optional
from core.config import (
    CATALOG_PATH, INDEXES_DIR, UPLOADS_DIR
)
from core.models import DocumentCatalogEntry, DocumentType
logger = logging.getLogger(__name__)
```
**Why hashlib?**
SHA256 hash of the file bytes. If two uploads produce the same hash, it's the same file. We reject the duplicate before doing any processing.
**Why shutil?**
When a document is deleted, we need to remove its FAISS index file, its chunks pkl file, and its uploaded PDF. `shutil` handles directory/file deletion cleanly.
---
```python
class DocumentStore:
    """
    Single source of truth for all uploaded documents.
    Wraps catalog.json with business logic:
    deduplication, deletion cascades, validation.
    """
    def __init__(self):
        self._ensure_catalog_exists()
    def _ensure_catalog_exists(self) -> None:
        if not CATALOG_PATH.exists():
            CATALOG_PATH.write_text("[]")
            logger.info("Created empty catalog.json")
    # ─── Hash ─────────────────────────────────────────────
    @staticmethod
    def compute_hash(file_bytes: bytes) -> str:
        return hashlib.sha256(file_bytes).hexdigest()
```
**Why static method?**
Hash computation doesn't need any instance state. Keeping it static means you can call `DocumentStore.compute_hash(bytes)` without instantiating the class — useful in the upload route before the store is fully involved.
---
```python
    # ─── Read ─────────────────────────────────────────────
    def load_all(self) -> list[DocumentCatalogEntry]:
        """Load all catalog entries from disk."""
        import json
        raw = json.loads(CATALOG_PATH.read_text())
        return [DocumentCatalogEntry(**entry) for entry in raw]
    def get_by_id(self, doc_id: str) -> Optional[DocumentCatalogEntry]:
        """Fetch one document by its ID. Returns None if not found."""
        for doc in self.load_all():
            if doc.doc_id == doc_id:
                return doc
        return None
    def get_by_hash(self, file_hash: str) -> Optional[DocumentCatalogEntry]:
        """Check if a file with this hash already exists — deduplication."""
        for doc in self.load_all():
            if doc.file_hash == file_hash:
                return doc
        return None
    def exists(self, doc_id: str) -> bool:
        return self.get_by_id(doc_id) is not None
```
**Why load_all every time?**
No caching for now — catalog.json is small and this keeps the code simple. If catalog grows to thousands of documents we add an in-memory cache layer. Premature optimization avoided.
---
```python
    # ─── Write ────────────────────────────────────────────
    def save(self, entry: DocumentCatalogEntry) -> None:
        """
        Add a new entry to catalog.json.
        Called after ingestion completes successfully.
        """
        import json
        all_docs = self.load_all()
        # Prevent duplicates by doc_id
        if any(d.doc_id == entry.doc_id for d in all_docs):
            logger.warning(f"doc_id {entry.doc_id} already exists, skipping save")
            return
        all_docs.append(entry)
        self._write(all_docs)
        logger.info(f"Saved document to catalog: {entry.title} ({entry.doc_id})")
    def update(self, updated_entry: DocumentCatalogEntry) -> None:
        """Replace an existing entry — used when chunk count is finalized."""
        all_docs = self.load_all()
        updated = [
            updated_entry if d.doc_id == updated_entry.doc_id else d
            for d in all_docs
        ]
        self._write(updated)
    def _write(self, entries: list[DocumentCatalogEntry]) -> None:
        import json
        CATALOG_PATH.write_text(
            json.dumps(
                [e.model_dump(mode="json") for e in entries],
                indent=2,
                default=str
            )
        )
```
**Why `model_dump(mode="json")`?**
Pydantic v2. This serializes datetime objects and enums to JSON-safe strings automatically. Without `mode="json"` you get Python objects that `json.dumps` can't handle.
---
```python
    # ─── Delete ───────────────────────────────────────────
    def delete(self, doc_id: str) -> bool:
        """
        Remove document from catalog AND delete all associated files:
        - FAISS index file
        - Chunks pkl file
        - Original uploaded PDF
        Returns True if deleted, False if doc_id not found.
        """
        doc = self.get_by_id(doc_id)
        if not doc:
            logger.warning(f"Delete called on unknown doc_id: {doc_id}")
            return False
        # Remove from catalog.json
        all_docs = self.load_all()
        remaining = [d for d in all_docs if d.doc_id != doc_id]
        self._write(remaining)
        # Delete FAISS index file
        self._safe_delete(Path(doc.index_path))
        # Delete chunks pkl file
        self._safe_delete(Path(doc.chunks_path))
        # Delete uploaded PDF
        pdf_path = UPLOADS_DIR / doc.filename
        self._safe_delete(pdf_path)
        logger.info(f"Deleted document: {doc.title} ({doc_id})")
        return True
    @staticmethod
    def _safe_delete(path: Path) -> None:
        """Delete a file if it exists. Never raises."""
        try:
            if path.exists():
                path.unlink()
                logger.debug(f"Deleted file: {path}")
        except Exception as e:
            logger.warning(f"Could not delete {path}: {e}")
```
**Why `_safe_delete`?**
Deletion should never crash the app. If the FAISS file is already missing for some reason, we log a warning and continue. The catalog entry still gets removed.
---
```python
    # ─── Validation & Helpers ─────────────────────────────
    def validate_doc_ids(self, doc_ids: list[str]) -> list[str]:
        """
        Filter a list of doc_ids to only those that actually exist.
        Used when user manually specifies which docs to search.
        """
        valid = []
        for doc_id in doc_ids:
            if self.exists(doc_id):
                valid.append(doc_id)
            else:
                logger.warning(f"Requested doc_id not found: {doc_id}")
        return valid
    def get_catalog_summary(self) -> list[dict]:
        """
        Lightweight summary of all docs for the agent's
        catalog-reading node — title, type, chapters, preview_text.
        No chunk data, no paths.
        """
        docs = self.load_all()
        return [
            {
                "doc_id": d.doc_id,
                "title": d.title,
                "doc_type": d.doc_type,
                "total_pages": d.total_pages,
                "chapters": [c.title for c in d.chapters],
                "domain_tags": d.domain_tags,
                "preview_text": d.preview_text[:500],  # trim for prompt
            }
            for d in docs
        ]
    def total_documents(self) -> int:
        return len(self.load_all())

# ─── Singleton ────────────────────────────────────────────────────────────────
document_store = DocumentStore()
```
**Why singleton at the bottom?**
Every file that needs the store just does `from core.document_store import document_store`. One instance, shared everywhere. No need to instantiate it repeatedly.
**Why `get_catalog_summary`?**
The agent's first node reads the catalog to decide which documents are relevant. It doesn't need index paths or chunk counts — it needs titles, chapter names, domain tags, and a preview of the text. This method returns exactly that, trimmed for prompt injection.
---
That's `core/document_store.py` fully explained.
Great question. You **can** do it normally — it would work fine:
```python
store = DocumentStore()
hash = store.compute_hash(file_bytes)
```
No error, no problem. So why bother with `@staticmethod`?
---
### It's about **communicating intent**
When another developer sees `@staticmethod`, it immediately tells them:
> *"This function doesn't touch the object at all — it's just a utility that happens to live here"*
Without it, they'd have to **read the whole function** to figure out whether it uses `self` or not.
---
### It's about **unnecessary work**
```python
store = DocumentStore()  # this runs __init__
                         # which calls _ensure_catalog_exists
                         # which hits the filesystem
                         # just to... compute a hash?
```
You're doing filesystem work for no reason, just to call a function that only needs `hashlib`.
---
### So why keep it inside the class at all?
You could put it outside as a plain function too:
```python
def compute_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()
```
That also works. But keeping it inside `DocumentStore` makes logical sense — hashing is **conceptually part of how the store identifies documents**. It belongs there, just doesn't need instance state.
---
### Short answer
| Approach | Works? | Problem |
|---|---|---|
| Plain function outside class | ✅ | Loses logical grouping |
| Regular method | ✅ | Misleads readers, wastes `__init__` |
| `@staticmethod` | ✅ | Clear, honest, efficient |
It's not about **making it work** — it's about **making it clear**.
## Full Breakdown
---
### `validate_doc_ids`
```python
def validate_doc_ids(self, doc_ids: list[str]) -> list[str]:
    valid = []
    for doc_id in doc_ids:
        if self.exists(doc_id):
            valid.append(doc_id)
        else:
            logger.warning(f"Requested doc_id not found: {doc_id}")
    return valid
```
User sends: `["abc", "def", "xyz"]`  
Only `"abc"` and `"def"` exist in catalog.
```
Input:  ["abc", "def", "xyz"]
                        ↑ doesn't exist → warning logged
Output: ["abc", "def"]
```
Instead of **crashing** when a bad ID is passed, it **silently filters it out** and continues with valid ones. Defensive programming — don't let one bad ID break the whole search.
---
### `get_catalog_summary`
```python
return [
    {
        "doc_id": d.doc_id,
        "title": d.title,
        "doc_type": d.doc_type,
        "total_pages": d.total_pages,
        "chapters": [c.title for c in d.chapters],
        "domain_tags": d.domain_tags,
        "preview_text": d.preview_text[:500],  # trim for prompt
    }
    for d in docs
]
```
This returns a **stripped down version** of each document — notice what's missing:
| Included | Excluded |
|---|---|
| title, doc_type | file paths |
| chapters, tags | chunk data |
| preview (500 chars) | full text |
| doc_id | file hash |
**Why trim?** This summary is fed directly into an **AI agent's prompt**. Sending full document data would:
- Waste tokens
- Bloat the context window
- Slow down the LLM
`d.preview_text[:500]` — the `[:500]` is Python slicing, takes only the first 500 characters.
`[c.title for c in d.chapters]` — extracts just chapter titles from chapter objects, not the full chapter data.
---
### `total_documents`
```python
def total_documents(self) -> int:
    return len(self.load_all())
```
Simple counter. Useful for UI stats like *"You have 12 documents uploaded"*.
---
### The Singleton — most important line
```python
document_store = DocumentStore()
```
This sits **outside the class**, at the module level. It creates **one single instance** for the entire application.
Every part of the app imports this one object:
```python
# anywhere in the codebase
from store import document_store
document_store.save(entry)
document_store.delete(doc_id)
document_store.load_all()
```
**Why singleton?** Because `catalog.json` is one file. If every request created its own `DocumentStore()`, you could get:
```
Request A loads catalog → 10 docs
Request B loads catalog → 10 docs
Request A saves doc 11  → writes 11 docs
Request B saves doc 11  → overwrites with 11 docs (data corruption!)
```
One shared instance = one source of truth = no conflicts.
---
### The full picture of the class
```
DocumentStore
│
├── Read      → load_all, get_by_id, get_by_hash, exists
├── Write     → save, update, _write
├── Delete    → delete, _safe_delete  
└── Helpers   → validate_doc_ids, get_catalog_summary, total_documents
         all sharing one catalog.json
         all accessed via one singleton: document_store
```
Why try/except at the top level?
Corrupted PDFs, password-protected files, zero-page documents — all of these will throw inside fitz. We catch everything and return UNKNOWN rather than crashing the upload pipeline.
<img width="836" height="20658" alt="image" src="https://github.com/user-attachments/assets/ebdf0f6a-0537-415b-9ac0-d5dd9b312440" />
