# PolyMath
polymath/
├── backend/
│   ├── main.py                          # FastAPI app entry point
│   ├── config.py                        # Env vars, constants, paths
│   ├── requirements.txt
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── detector.py                  # Book vs paper detection logic
│   │   ├── extractor.py                 # PyMuPDF + pdfplumber catalog extraction
│   │   ├── chunker.py                   # Page-by-page chunking + tagging
│   │   ├── embedder.py                  # sentence-transformers embedding
│   │   └── indexer.py                   # Per-document FAISS index builder
│   │
│   ├── catalog/
│   │   ├── __init__.py
│   │   └── manager.py                   # Read/write catalog.json
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── graph.py                     # LangGraph graph definition
│   │   ├── nodes.py                     # All node functions (catalog read, retrieval, generation, eval)
│   │   ├── state.py                     # AgentState TypedDict
│   │   └── prompts.py                   # All prompt templates
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   └── retriever.py                 # Per-doc FAISS query logic
│   │
│   ├── evaluation/
│   │   ├── __init__.py
│   │   └── ragas_eval.py                # Background RAGAS scoring + retry trigger
│   │
│   ├── memory/
│   │   ├── __init__.py
│   │   └── session.py                   # In-memory session history store
│   │
│   └── api/
│       ├── __init__.py
│       ├── routes_upload.py             # POST /upload
│       ├── routes_query.py              # POST /query, POST /synthesize
│       ├── routes_catalog.py            # GET /catalog, DELETE /document/{id}
│       └── routes_eval.py              # GET /scores
│
├── storage/
│   ├── indexes/                         # FAISS index files per doc (auto-created)
│   ├── uploads/                         # Raw uploaded PDFs (auto-created)
│   └── catalog.json                     # Master catalog (auto-created)
│
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── api/
        │   └── client.ts                # Axios API client
        ├── components/
        │   ├── ChatWindow.tsx           # Main chat area
        │   ├── MessageBubble.tsx        # Single message with citations
        │   ├── ModeToggle.tsx           # Q&A / Synthesize toggle
        │   ├── Sidebar.tsx              # Document list + metadata
        │   ├── DocumentCard.tsx         # Single doc in sidebar
        │   ├── UploadZone.tsx           # Drag-and-drop upload
        │   ├── ScoresBadge.tsx          # RAGAS scores display
        │   └── SynthesisOutput.tsx      # Formatted synthesis markdown
        ├── store/
        │   └── usePolymathStore.ts      # Zustand global state
        └── types/
            └── index.ts                 # Shared TypeScript types

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



polymath/
│
├── ingestion/
│   ├── __init__.py
│   ├── parser.py               ← PDF text extraction (PyMuPDF)
│   ├── chunker.py              ← smart chunking (semantic + parent-child)
│   ├── embedder.py             ← contextual embeddings → ChromaDB
│   └── contextualizer.py       ← LLM adds doc-level context to each chunk
│
├── retrieval/
│   ├── __init__.py
│   ├── base_retriever.py       ← BM25 + ChromaDB hybrid, RRF merge
│   ├── hyde.py                 ← HyDE: generate hypothetical doc, embed that
│   ├── multi_query.py          ← decompose query → parallel retrieval
│   ├── compressor.py           ← contextual compression of retrieved chunks
│   └── graph_retriever.py      ← GraphRAG: entity graph, relationship traversal
│
├── agents/
│   ├── __init__.py
│   ├── router_agent.py         ← detects use case, picks retrieval strategy
│   ├── query_agent.py          ← query analysis, decomposition, rewriting
│   ├── crag_agent.py           ← corrective RAG: grades chunks, re-retrieves if bad
│   └── self_rag_agent.py       ← reflection: is answer grounded? loop if not
│
├── synthesis/
│   ├── __init__.py
│   ├── comparator.py           ← cross-document: agreements, contradictions, gaps
│   └── summarizer.py           ← multi-book unified synthesis
│
├── graph/
│   ├── __init__.py
│   ├── entity_extractor.py     ← extract entities + relationships from chunks
│   ├── graph_builder.py        ← build NetworkX graph from entities
│   └── graph_store.py          ← persist graph to Neo4j or local JSON
│
├── eval/
│   ├── __init__.py
│   ├── golden_dataset.py       ← create Q&A pairs for evaluation
│   └── ragas_eval.py           ← faithfulness, context recall, answer relevancy
│
├── api/
│   ├── __init__.py
│   ├── main.py                 ← FastAPI app, CORS, lifespan
│   ├── routes/
│   │   ├── upload.py           ← POST /upload, triggers ingestion pipeline
│   │   ├── query.py            ← POST /query, triggers agent pipeline
│   │   └── analysis.py         ← POST /analyze, triggers synthesis pipeline
│   └── schemas.py              ← Pydantic request/response models
│
├── core/
│   ├── __init__.py
│   ├── config.py               ← all env vars, model names, constants
│   ├── pipeline.py             ← orchestrates full end-to-end flow
│   └── document_store.py       ← tracks uploaded docs, metadata, hashes
│
├── tests/
│   ├── test_ingestion.py
│   ├── test_retrieval.py
│   └── test_agents.py
│
├── .env
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md