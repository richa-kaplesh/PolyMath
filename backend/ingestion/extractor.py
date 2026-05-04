# backend/ingestion/extractor.py

import re
import pdfplumber
import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional
from backend.core.config import CATALOG_PREVIEW_PAGES


def extract_metadata(pdf_path: str) -> dict:
    """
    Extracts title, author, page count, and a short preview snippet.
    
    Strategy:
      - fitz (PyMuPDF) for embedded PDF metadata (fast, reliable)
      - pdfplumber fallback: scrape title from first page text if metadata empty
    """
    path = str(pdf_path)
    meta = {}

    # --- PyMuPDF: embedded metadata ---
    doc = fitz.open(path)
    raw_meta = doc.metadata  # dict: title, author, subject, creator, etc.
    doc.close()

    meta["title"]  = _clean(raw_meta.get("title", ""))
    meta["author"] = _clean(raw_meta.get("author", ""))

    # --- pdfplumber: page count + preview + fallback title ---
    with pdfplumber.open(path) as pdf:
        meta["page_count"] = len(pdf.pages)

        # Build a short preview from first CATALOG_PREVIEW_PAGES pages
        preview_text = ""
        for page in pdf.pages[:CATALOG_PREVIEW_PAGES]:
            preview_text += (page.extract_text() or "") + "\n"

        meta["preview"] = preview_text[:500].strip()

        # Fallback: if embedded title missing, grab first non-empty line
        if not meta["title"]:
            meta["title"] = _extract_title_from_text(preview_text)

    return meta


def extract_pages(pdf_path: str) -> list[dict]:
    """
    Extracts text from every page.
    Returns a list of dicts: { page_number (1-indexed), text }

    Strategy:
      - pdfplumber first (better for columnar/table-heavy layouts)
      - fitz fallback per page if pdfplumber yields empty text
    """
    path = str(pdf_path)
    pages = []

    with pdfplumber.open(path) as pdf:
        fitz_doc = fitz.open(path)

        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""

            # Fallback to fitz if pdfplumber gave us nothing
            if not text.strip():
                fitz_page = fitz_doc.load_page(i)
                text = fitz_page.get_text("text") or ""

            pages.append({
                "page_number": i + 1,   # 1-indexed, human-friendly
                "text": text.strip(),
            })

        fitz_doc.close()

    return pages


def _clean(value: str) -> str:
    """Strip null bytes, extra whitespace from PDF metadata strings."""
    return re.sub(r'\s+', ' ', value.replace('\x00', '')).strip()


def _extract_title_from_text(text: str) -> str:
    """
    Grab the first non-empty line as a best-guess title.
    Caps at 120 chars to avoid grabbing a paragraph.
    """
    for line in text.splitlines():
        line = line.strip()
        if len(line) > 4:           # skip single chars / page numbers
            return line[:120]
    return "Untitled"