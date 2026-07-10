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

import ipaddress
import re
import logging
import socket
from io import BytesIO
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from pypdf import PdfReader
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Cap fetched URL bodies — a vendor security page should never be this big
MAX_URL_BYTES = 10 * 1024 * 1024


class UnsafeURLError(ValueError):
    """Raised when a URL targets a private, loopback, or reserved address (SSRF guard)."""


class ScannedPDFError(ValueError):
    """Raised when a PDF has pages but effectively no extractable text (needs OCR)."""


def _assert_public_http_url(url: str) -> None:
    """Reject URLs that could reach internal services (SSRF guard).

    Only http/https schemes are allowed, and every resolved address for
    the hostname must be a public (global) IP — this blocks localhost,
    RFC-1918 ranges, link-local (including cloud metadata at
    169.254.169.254), and other reserved space.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError(f"Only http/https URLs are allowed (got '{parsed.scheme or 'none'}')")
    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL has no hostname")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise UnsafeURLError(f"Could not resolve host '{host}'") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise UnsafeURLError(
                f"URL resolves to a non-public address ({ip}) — refusing to fetch"
            )


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

    # Honest failure for scanned/image-only PDFs: silently ingesting zero
    # text would produce an all-NO_EVIDENCE assessment that looks like a
    # vendor problem when it's actually an input problem.
    total_chars = sum(len(p.text) for p in pages)
    if len(reader.pages) > 0 and total_chars < 40 * len(reader.pages):
        raise ScannedPDFError(
            f"'{filename}' appears to be a scanned/image-only PDF — "
            f"{len(reader.pages)} page(s) yielded almost no extractable text. "
            "Run it through OCR first, or upload a text-based export."
        )

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
        UnsafeURLError: If the URL (or any redirect hop) targets a
            private/reserved address — SSRF guard.
        ValueError: If the page yields less than 10 characters of text.
        httpx.HTTPError: On network errors.
    """
    # Follow redirects MANUALLY so every hop is re-validated — otherwise a
    # public URL could 302 to http://169.254.169.254/ or an internal service.
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; VendorShield/1.0)",
        "Accept": "text/html,application/xhtml+xml,text/plain,*/*",
    }
    current = url
    response: httpx.Response | None = None
    for _hop in range(4):
        _assert_public_http_url(current)
        response = httpx.get(current, headers=headers, timeout=30, follow_redirects=False)
        if response.status_code in (301, 302, 303, 307, 308) and response.headers.get("location"):
            current = str(response.next_request.url) if response.next_request else response.headers["location"]
            continue
        break
    else:
        raise ValueError("Too many redirects")
    assert response is not None
    response.raise_for_status()

    if len(response.content) > MAX_URL_BYTES:
        raise ValueError(
            f"URL content too large ({len(response.content) // (1024 * 1024)} MB, max {MAX_URL_BYTES // (1024 * 1024)} MB)"
        )

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
