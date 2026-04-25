# backend/ingestion/detector.py

import re
from pdfplumber import open as plumber_open
from config import (
    BOOK_TOC_ENTRY_THRESHOLD,
    BOOK_PAGE_THRESHOLD,
    PAPER_KEYWORDS,
    CATALOG_PREVIEW_PAGES,
)


def detect_document_type(pdf_path: str) -> str:
    """
    Returns 'book' or 'paper' based on structural heuristics.

    Heuristics:
      1. Page count   — books tend to be longer
      2. TOC presence — books have tables of contents
      3. Keyword scan — papers contain academic section headers
    """
    with plumber_open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

        # Heuristic 1: raw page count
        if total_pages >= BOOK_PAGE_THRESHOLD:
            page_score = 1
        else:
            page_score = 0

        # Heuristic 2: TOC detection
        # Scan first CATALOG_PREVIEW_PAGES pages for TOC-like patterns
        # TOC lines look like:  "Chapter 3 .... 42"  or  "3. Some Title ... 42"
        toc_pattern = re.compile(
            r'(chapter|\bpart\b|section)?\s*\d+[\.\s].{3,60}\.{2,}\s*\d+',
            re.IGNORECASE
        )
        toc_hits = 0
        for page in pdf.pages[:CATALOG_PREVIEW_PAGES]:
            text = page.extract_text() or ""
            toc_hits += len(toc_pattern.findall(text))

        toc_score = 1 if toc_hits >= BOOK_TOC_ENTRY_THRESHOLD else 0

        # Heuristic 3: academic keyword scan in first few pages
        keyword_hits = 0
        for page in pdf.pages[:CATALOG_PREVIEW_PAGES]:
            text = (page.extract_text() or "").lower()
            for kw in PAPER_KEYWORDS:
                if kw in text:
                    keyword_hits += 1

        # Papers usually hit multiple keywords; threshold = half the list
        paper_score = 1 if keyword_hits >= (len(PAPER_KEYWORDS) // 2) else 0

        # Decision: majority vote across 3 signals
        book_votes  = page_score + toc_score
        paper_votes = paper_score

        # Tie-break: if scores equal, lean toward 'paper' (safer default)
        return "book" if book_votes > paper_votes else "paper"