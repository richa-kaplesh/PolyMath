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

        for keyword in PAPER_KEYWORDS:
            if keyword in PAPER_KEYWORDS:
                paper_score +=1
        for keyword in BOOK_KEYWORDS:
            if keyword in preview_text:
                book_score +=1  
        
        last_page_text = ""
        if doc.page_count >0:
            last_page_text = doc[doc.page_count -1].get_text().lower
            
        if "references" in last_page_text or "bibiliography" in last_page_text:
            paper_score += 1 
        
        logger.debug(
            f"Detection scores - paper: {paper_score},book: {book_score}"
            f"| pages: {total_pages},toc_entries:{len(toc) if toc else 0}"
        )

        if paper_score > book_score and paper_score >= self.CONFIDENCE_THRESHOLD:
            return DocumentType.PAPER
        elif book_score >paper_score and book_score 