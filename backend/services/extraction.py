"""
Layer 3: Text Extraction from PDF, DOCX, and URL sources.

RESPONSIBILITY:
    Reads files or fetches URLs and returns raw text.  That is all.
    No chunking, no embedding, no database calls.

    Supported formats:
    - PDF  → pypdf
    - DOCX → python-docx
    - Plain text / other → decoded as UTF-8
    - URL  → requests + BeautifulSoup (HTML stripping)

IMPORTS FROM: nothing (no backend dependencies)
IMPORTED BY:  services/ingestion.py
"""

import re
import logging
from io import BytesIO
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from pypdf import PdfReader
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ExtractedPage:
    """A page (or section) of extracted text with source metadata."""
    text: str
    page_number: int
    source: str  # filename or URL display name


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------


def extract_pdf(file_bytes: bytes, filename: str) -> list[ExtractedPage]:
    """Extract text from a PDF file, preserving page numbers.

    Args:
        file_bytes: Raw PDF file content.
        filename: Original filename (used as source metadata).

    Returns:
        List of ExtractedPage, one per non-empty page.
    """
    reader = PdfReader(BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(ExtractedPage(
                text=text.strip(),
                page_number=i + 1,
                source=filename,
            ))
    logger.info(f"Extracted {len(pages)} pages from PDF '{filename}'")
    return pages


# ---------------------------------------------------------------------------
# DOCX / plain text extraction
# ---------------------------------------------------------------------------


def extract_text_file(file_bytes: bytes, filename: str) -> list[ExtractedPage]:
    """Extract text from a DOCX or plain text file.

    Routes .docx files to the DOCX extractor; everything else is
    decoded as UTF-8 plain text.
    """
    if filename.lower().endswith(".docx"):
        return _extract_docx(file_bytes, filename)

    text = file_bytes.decode("utf-8", errors="replace")
    if not text.strip():
        return []

    logger.info(f"Extracted text from '{filename}' ({len(text)} chars)")
    return [ExtractedPage(text=text.strip(), page_number=1, source=filename)]


def _extract_docx(file_bytes: bytes, filename: str) -> list[ExtractedPage]:
    """Extract text from a DOCX file using python-docx."""
    from docx import Document

    doc = Document(BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs)

    if not text.strip():
        return []

    logger.info(f"Extracted {len(paragraphs)} paragraphs from DOCX '{filename}'")
    return [ExtractedPage(text=text.strip(), page_number=1, source=filename)]


# ---------------------------------------------------------------------------
# URL extraction
# ---------------------------------------------------------------------------


def extract_url(url: str) -> list[ExtractedPage]:
    """Fetch a URL and extract its text content.

    Uses requests (sync) + BeautifulSoup for HTML stripping.
    For plain text or JSON responses, returns the raw content directly.

    Raises:
        ValueError: If the page yields less than 10 characters of text.
        requests.RequestException: On network errors.
    """
    response = httpx.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; VendorShield/1.0)",
            "Accept": "text/html,application/xhtml+xml,text/plain,*/*",
        },
        timeout=30,
        follow_redirects=True,
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")

    if "text/plain" in content_type or "application/json" in content_type:
        raw_text = response.text
    else:
        raw_text = _strip_html(response.text)

    if not raw_text or len(raw_text.strip()) < 10:
        raise ValueError(
            "Could not extract meaningful text from URL. "
            "Page may require JavaScript."
        )

    # Build a readable display name from the URL
    parsed = urlparse(url)
    display_name = f"{parsed.hostname}{parsed.path}".rstrip("/")

    logger.info(f"Extracted {len(raw_text)} chars from URL '{display_name}'")
    return [ExtractedPage(text=raw_text.strip(), page_number=1, source=display_name)]


def _strip_html(html: str) -> str:
    """Strip HTML tags and extract clean text using BeautifulSoup.

    Removes non-content elements (scripts, nav, footer, etc.)
    and normalizes whitespace.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "noscript", "svg", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text
