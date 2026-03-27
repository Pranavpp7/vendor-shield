"""Text chunking with overlap and metadata preservation."""

from dataclasses import dataclass
from services.extraction import ExtractedPage


@dataclass
class Chunk:
    content: str
    chunk_index: int
    page_number: int
    source: str  # document name or URL


def split_into_chunks(
    pages: list[ExtractedPage],
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> list[Chunk]:
    """Split extracted pages into overlapping word-based chunks.

    Preserves page number and source document metadata per chunk.
    """
    chunks: list[Chunk] = []
    global_index = 0

    for page in pages:
        words = page.text.split()
        if not words:
            continue

        if len(words) <= chunk_size:
            chunks.append(Chunk(
                content=" ".join(words),
                chunk_index=global_index,
                page_number=page.page_number,
                source=page.source,
            ))
            global_index += 1
        else:
            i = 0
            while i < len(words):
                chunk_words = words[i: i + chunk_size]
                chunk_text = " ".join(chunk_words).strip()
                if chunk_text:
                    chunks.append(Chunk(
                        content=chunk_text,
                        chunk_index=global_index,
                        page_number=page.page_number,
                        source=page.source,
                    ))
                    global_index += 1
                i += chunk_size - chunk_overlap

    return chunks
