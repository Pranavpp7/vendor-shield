"""
Layer 3: Text Chunking.

RESPONSIBILITY:
    Splits a plain text string into overlapping chunks suitable for
    embedding and vector search.  That is all.
    No extraction, no embedding, no database calls.

    Uses LangChain RecursiveCharacterTextSplitter which tries to split
    at natural boundaries (paragraphs, sentences, words) before falling
    back to raw character splits.

    chunk_size and chunk_overlap are specified in WORDS in config.py,
    but RecursiveCharacterTextSplitter works in characters.  We convert
    using an average of 6 characters per English word.

IMPORTS FROM: config.py (for chunk_size, chunk_overlap)
IMPORTED BY:  services/ingestion.py
"""

import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter
from config import get_settings

logger = logging.getLogger(__name__)

# Average characters per English word (including trailing space).
# Used to convert word-based config values to character counts.
CHARS_PER_WORD = 6


def split_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """Split a plain text string into overlapping chunks.

    Args:
        text: The full document text to split.
        chunk_size: Max chunk size in words.  Defaults to config value (500).
        chunk_overlap: Overlap between chunks in words.  Defaults to config (50).

    Returns:
        List of text chunk strings.  Empty list if input text is empty.
    """
    if not text or not text.strip():
        return []

    settings = get_settings()
    size_words = chunk_size or settings.chunk_size      # 500 words
    overlap_words = chunk_overlap or settings.chunk_overlap  # 50 words

    # Convert words → characters for LangChain splitter
    size_chars = size_words * CHARS_PER_WORD       # 500 × 6 = 3000 chars
    overlap_chars = overlap_words * CHARS_PER_WORD  # 50 × 6 = 300 chars

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size_chars,
        chunk_overlap=overlap_chars,
        separators=["\n\n", "\n", ". ", " "],
        length_function=len,
        is_separator_regex=False,
    )

    chunks = splitter.split_text(text)

    logger.info(
        f"Split {len(text)} chars into {len(chunks)} chunks "
        f"(size={size_words}w, overlap={overlap_words}w)"
    )
    return chunks
