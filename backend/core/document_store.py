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

    @staticmethod
    def compute_hash(file_bytes: bytes) -> str:
        return hashlib.sha256(file_bytes).hexdigest()

    
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
                "preview_text": d.preview_text[:500],  
            }
            for d in docs
        ]

    def total_documents(self) -> int:
        return len(self.load_all())

document_store = DocumentStore()