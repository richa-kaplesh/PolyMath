# backend/ingestion/embedder.py

import numpy as np
from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL, EMBEDDING_DIM

# Load model once at module level — expensive operation, don't reload per call
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """
    Lazy singleton loader.
    Model is downloaded on first call, reused after.
    """
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Adds an 'embedding' key to each chunk dict.

    Args:
        chunks: output of chunker.chunk_pages()

    Returns:
        Same list with 'embedding' added — shape (EMBEDDING_DIM,), normalized
    """
    model = _get_model()

    # Extract raw texts for batch encoding
    texts = [chunk["text"] for chunk in chunks]

    # Batch encode — much faster than encoding one by one
    # normalize_embeddings=True → unit vectors → cosine sim becomes dot product
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=False,
        normalize_embeddings=True,  # Topic: L2 Normalization for Cosine Similarity
    )

    # embeddings shape: (num_chunks, EMBEDDING_DIM)
    # Validate dimension matches config
    if embeddings.shape[1] != EMBEDDING_DIM:
        raise ValueError(
            f"Embedding dim mismatch: expected {EMBEDDING_DIM}, got {embeddings.shape[1]}"
        )

    # Attach embedding to each chunk as a plain Python list
    # list (not np.array) so it's JSON-serializable if needed later
    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding.tolist()

    return chunks


def embed_query(query: str) -> np.ndarray:
    """
    Embeds a single query string at retrieval time.

    Returns:
        np.ndarray of shape (EMBEDDING_DIM,), normalized
    """
    model = _get_model()

    embedding = model.encode(
        query,
        normalize_embeddings=True,
    )

    return np.array(embedding, dtype=np.float32)