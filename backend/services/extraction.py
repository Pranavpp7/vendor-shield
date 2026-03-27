"""Text extraction from PDFs, URLs, and DOCX files."""

import httpx
from pypdf import PdfReader
from bs4 import BeautifulSoup
from io import BytesIO
from dataclasses import dataclass


@dataclass
class ExtractedPage:
    text: str
    page_number: int
    source: str  # filename or URL


def extract_pdf(file_bytes: bytes, filename: str) -> list[ExtractedPage]:
    """Extract text from a PDF file, preserving page numbers."""
    reader = PdfReader(BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(ExtractedPage(text=text.strip(), page_number=i + 1, source=filename))
    return pages


def extract_text_file(file_bytes: bytes, filename: str) -> list[ExtractedPage]:
    """Extract text from a plain text or DOCX file."""
    if filename.endswith(".docx"):
        return _extract_docx(file_bytes, filename)
    text = file_bytes.decode("utf-8", errors="replace")
    return [ExtractedPage(text=text.strip(), page_number=1, source=filename)] if text.strip() else []


def _extract_docx(file_bytes: bytes, filename: str) -> list[ExtractedPage]:
    """Extract text from a DOCX file."""
    from docx import Document

    doc = Document(BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs)
    return [ExtractedPage(text=text.strip(), page_number=1, source=filename)] if text.strip() else []


async def extract_url(url: str) -> list[ExtractedPage]:
    """Fetch and extract text from a URL."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        response = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; VendorShield/1.0)",
            "Accept": "text/html,application/xhtml+xml,text/plain,*/*",
        })
        response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    html = response.text

    if "text/plain" in content_type or "application/json" in content_type:
        raw_text = html
    else:
        raw_text = _strip_html(html)

    if not raw_text or len(raw_text.strip()) < 10:
        raise ValueError("Could not extract meaningful text from URL. Page may require JavaScript.")

    # Parse URL for display name
    from urllib.parse import urlparse
    parsed = urlparse(url)
    display_name = f"{parsed.hostname}{parsed.path}".rstrip("/")

    return [ExtractedPage(text=raw_text.strip(), page_number=1, source=display_name)]


def _strip_html(html: str) -> str:
    """Strip HTML tags and extract clean text using BeautifulSoup."""
    soup = BeautifulSoup(html, "html.parser")
    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    # Normalize whitespace
    import re
    text = re.sub(r"\s+", " ", text).strip()
    return text
