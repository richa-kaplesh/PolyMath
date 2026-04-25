import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR     = Path(__file__).resolve().parent.parent   # project root
STORAGE_DIR  = BASE_DIR / "storage"
UPLOADS_DIR  = STORAGE_DIR / "uploads"
INDEXES_DIR  = STORAGE_DIR / "indexes"
CATALOG_PATH = STORAGE_DIR / "catalog.json"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
INDEXES_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
LLM_MODEL      = os.getenv("LLM_MODEL", "llama3-70b-8192")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
MAX_TOKENS     = int(os.getenv("MAX_TOKENS", "2048"))


EMBEDDING_MODEL    = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM      = 384

CHUNK_SIZE         = int(os.getenv("CHUNK_SIZE", "500"))   
CHUNK_OVERLAP      = int(os.getenv("CHUNK_OVERLAP", "50"))

TOP_K_PER_DOC      = int(os.getenv("TOP_K_PER_DOC", "5"))
MAX_DOCS_IN_CONTEXT = int(os.getenv("MAX_DOCS_IN_CONTEXT", "5"))

RAGAS_FAITHFULNESS_THRESHOLD    = float(os.getenv("RAGAS_FAITHFULNESS_THRESHOLD", "0.7"))
RAGAS_RELEVANCE_THRESHOLD       = float(os.getenv("RAGAS_RELEVANCE_THRESHOLD", "0.7"))
RAGAS_PRECISION_THRESHOLD       = float(os.getenv("RAGAS_PRECISION_THRESHOLD", "0.6"))
RAGAS_MAX_RETRIES               = int(os.getenv("RAGAS_MAX_RETRIES", "1"))
EVAL_SCORES_PATH                = STORAGE_DIR / "eval_scores.json"

BOOK_TOC_ENTRY_THRESHOLD        = int(os.getenv("BOOK_TOC_ENTRY_THRESHOLD", "6"))
BOOK_PAGE_THRESHOLD             = int(os.getenv("BOOK_PAGE_THRESHOLD", "60"))

PAPER_KEYWORDS = [
    "abstract", "introduction", "methodology", "related work",
    "literature review", "conclusion", "references", "arxiv",
    "doi", "journal", "proceedings", "ieee", "acm"
]

CATALOG_PREVIEW_PAGES           = 5

MAX_HISTORY_TURNS               = int(os.getenv("MAX_HISTORY_TURNS", "10"))


API_HOST    = os.getenv("API_HOST", "0.0.0.0")
API_PORT    = int(os.getenv("API_PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

SYNTHESIS_MIN_SOURCES           = 2
SYNTHESIS_MAX_CHUNK_CHARS       = int(os.getenv("SYNTHESIS_MAX_CHUNK_CHARS", "6000"))
