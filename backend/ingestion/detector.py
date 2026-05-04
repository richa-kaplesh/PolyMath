import logging
from pathlib import Path

import fitz  # PyMuPDF

from core.config import (
    PAPER_MAX_PAGES,
    PAPER_KEYWORDS,
    BOOK_KEYWORDS,
)
from core.models import DocumentType

logger = logging.getLogger(__name__)

class DocumentDetector:
    CONFIDENCE_THRESHOLD =2

    def detect(self, pdf_path:Path) -> DocumentType:
        try:
            doc = fitz.open(str(pdf_path))
            result = self._classify(doc)
            doc.close()
            return result
        except Exception as e:
            logger.error(f"Error occurred while detecting document type for {pdf_path}: {e}")
            raise DocumentType.UNKNOWN
        
    def _classify(self, doc: fitz.Document) -> DocumentType:
        paper_score =0
        book_score = 0

        total_pages = doc.page_count
        if total_pages <= PAPER_MAX_PAGES:
            paper_score +=2
        elif total_pages >= 100:
            book_score += 2 
        else:
            book_score +=1
        
        toc= doc.get_toc()
        if toc:
            if len(toc) >=5:
                book_score += 3
            elif len(toc) >=2:
                book_score += 1
            else:
                paper_score += 1
        preview_text = self._extract_preview(doc).lower()