# backend/ingestion/chunker.py

from typing import List
from backend.core.config import CHUNK_SIZE, CHUNK_OVERLAP


def chunk_pages(
    pages: list[dict],
    doc_id: str,
    doc_type: str,
) -> list[dict]:
    """
    Converts extracted pages into overlapping text chunks.

    Each chunk carries metadata so the retriever knows exactly
    where it came from — critical for citations.

    Args:
        pages    : output of extractor.extract_pages()
        doc_id   : unique document identifier from catalog
        doc_type : 'book' or 'paper'

    Returns:
        list of chunk dicts
    """
    chunks = []
    chunk_index = 0

    for page in pages:
        page_number = page["page_number"]
        text        = page["text"]

        if not text.strip():
            continue

        # Split page text into overlapping windows
        page_chunks = _sliding_window(text)

        for chunk_text in page_chunks:
            if not chunk_text.strip():
                continue

            chunks.append({
                "chunk_id"   : f"{doc_id}_chunk_{chunk_index}",
                "doc_id"     : doc_id,
                "doc_type"   : doc_type,
                "page_number": page_number,
                "text"       : chunk_text.strip(),
                "chunk_index": chunk_index,
            })
            chunk_index += 1

    return chunks


def _sliding_window(text: str) -> list[str]:
    """
    Splits text into chunks of CHUNK_SIZE words with CHUNK_OVERLAP word overlap.

    Word-level (not character-level) because:
      - Embeddings care about semantic units, not byte counts
      - Avoids cutting mid-sentence arbitrarily
    
    Topic: Sliding Window Chunking
    """
    words = text.split()

    if not words:
        return []

    # If the entire page fits in one chunk, no splitting needed
    if len(words) <= CHUNK_SIZE:
        return [" ".join(words)]

    chunks = []
    start  = 0

    while start < len(words):
        end        = start + CHUNK_SIZE
        chunk      = words[start:end]
        chunks.append(" ".join(chunk))

        # Advance by (CHUNK_SIZE - CHUNK_OVERLAP) to create overlap
        # Overlap ensures context at chunk boundaries isn't lost
        start += CHUNK_SIZE - CHUNK_OVERLAP

        # Safety: if remaining words are less than overlap size, stop
        # Otherwise we'd create a near-duplicate final chunk
        if start >= len(words):
            break
        if len(words) - start <= CHUNK_OVERLAP:
            # Grab the tail and stop
            tail = words[start:]
            if tail:
                chunks.append(" ".join(tail))
            break

    return chunks