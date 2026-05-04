import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR     = Path(__file__).resolve().parent.parent   

GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY","")

LLM_MODEL : str = "llama3-8b-8192"
LLM_MAX_TOKENS: int = 1024
LLM_TEMPERATURE : float = 0.0
EMBEDDING_MODEL: str ="BAAI/bge-small-en-v1.5"
EMBEDDING_DIM: int = 384

EMBEDDING_BATCH_SIZE: int = 32

CHROMA_DIR: str = str(BASE_DIR/"chroma_store")
CHROMA_COLLECTION :str = "polymath_docs"


PARENT_CHUNK_SIZE: int = 1024
CHILD_CHUNK_SIZE: int = 256

CHUNK_OVERLAP : int = 50

RETRIEVAL_TOP_K: int = 10
FINAL_TOP_K: int = 5

BM_25_WEIGHT:float = 0.5
DENSE_WEIGHT:float = 0.5

GRAPH_STORE_PATH: str = str(BASE_DIR / "graph_store" / "graph.json")

UPLOAD_DIR: str = str(BASE_DIR/"uploads")
GRAPH_STORE_PATH: str = str(BASE_DIR / "graph_store" / "graph.json")

def validate_config()->None:
    errors=[]

    if not GROQ_API_KEY:
        errors.append("GROQ_API_KEY is not set in environment variables.")

    if errors:
        raise EnvironmentError(
        "Polymath configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
    )

    Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(GRAPH_STORE_PATH).parent.mkdir(parents=True, exist_ok=True)

validate_config()