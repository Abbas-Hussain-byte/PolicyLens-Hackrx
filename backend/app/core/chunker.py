"""Smart document chunking for insurance policies.

Strategy priority:
1. Section-based splitting (Section X, Article X, numbered headers)
2. Clause-based splitting (Clause, Provision, Exclusion patterns)
3. Paragraph-based splitting (double newlines)
4. Sliding window fallback (reused from original codebase)

Each chunk carries metadata for source citation.
"""

import re
from dataclasses import dataclass, field
from app.core.parser import ParsedDocument, PageText
import logging

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A text chunk with source metadata for citation."""
    text: str
    chunk_id: int = 0
    page_numbers: list[int] = field(default_factory=list)
    section_title: str = ""
    chunk_type: str = "general"  # general, coverage, exclusion, definition, claim, eligibility
    policy_id: str = ""
    char_start: int = 0
    char_end: int = 0

    @property
    def word_count(self) -> int:
        return len(self.text.split())


# Patterns for detecting section headers in insurance documents
SECTION_PATTERNS = [
    r'(?:^|\n)((?:Section|SECTION)\s+\d+[\.\:]?\s*[^\n]*)',
    r'(?:^|\n)((?:Article|ARTICLE)\s+\d+[\.\:]?\s*[^\n]*)',
    r'(?:^|\n)((?:Part|PART)\s+[IVXLCDM\d]+[\.\:]?\s*[^\n]*)',
    r'(?:^|\n)(\d+\.\s+[A-Z][^\n]{5,})',  # "1. Coverage Details"
    r'(?:^|\n)(\d+\.\d+\s+[A-Z][^\n]{5,})',  # "1.1 General Conditions"
]

# Patterns for chunk type classification
TYPE_PATTERNS = {
    "exclusion": r'(?i)(exclusion|excluded|not\s+cover|not\s+payable|not\s+eligible|exception|limitation)',
    "coverage": r'(?i)(cover|benefit|payable|eligible\s+for|entitled|included)',
    "definition": r'(?i)(means|defined\s+as|refers\s+to|definition|interpretation)',
    "claim": r'(?i)(claim|document|submit|notification|intimation|procedure|process)',
    "eligibility": r'(?i)(eligib|pre.?existing|waiting\s+period|condition|qualify)',
    "premium": r'(?i)(premium|payment|renewal|installment|amount\s+payable)',
}


def chunk_document(
    document: ParsedDocument,
    policy_id: str = "",
    max_chunk_size: int = 500,
    min_chunk_size: int = 80,
    overlap_words: int = 40,
) -> list[Chunk]:
    """Chunk a parsed document using smart strategies.

    Tries section-aware chunking first, falls back to sliding window.

    Args:
        document: Parsed PDF document.
        policy_id: ID of the policy for metadata.
        max_chunk_size: Maximum words per chunk.
        min_chunk_size: Minimum words per chunk (smaller chunks get merged).
        overlap_words: Word overlap for sliding window fallback.

    Returns:
        List of Chunk objects with metadata.
    """
    # Build page-to-text mapping for source tracking
    page_texts = {p.page_number: p.text for p in document.pages}
    full_text = document.full_text

    if not full_text.strip():
        logger.warning(f"Empty document: {document.filename}")
        return []

    # Try section-based chunking first
    chunks = _section_based_chunking(full_text, page_texts, max_chunk_size, min_chunk_size)

    # Fallback to sliding window if section chunking produces too few chunks
    if len(chunks) < 3:
        logger.info(f"Section chunking produced {len(chunks)} chunks, using sliding window")
        chunks = _sliding_window_chunking(full_text, page_texts, max_chunk_size, overlap_words)

    # Assign metadata to all chunks
    for i, chunk in enumerate(chunks):
        chunk.chunk_id = i
        chunk.policy_id = policy_id
        chunk.chunk_type = _classify_chunk(chunk.text)

    logger.info(f"Created {len(chunks)} chunks for {document.filename}")
    return chunks


def _section_based_chunking(
    full_text: str,
    page_texts: dict[int, str],
    max_chunk_size: int,
    min_chunk_size: int,
) -> list[Chunk]:
    """Split text by section headers."""
    # Find all section boundaries
    boundaries = []
    for pattern in SECTION_PATTERNS:
        for match in re.finditer(pattern, full_text):
            boundaries.append((match.start(), match.group(1).strip()))

    if not boundaries:
        return []

    # Sort by position
    boundaries.sort(key=lambda x: x[0])

    chunks = []
    for i, (start, title) in enumerate(boundaries):
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(full_text)
        section_text = full_text[start:end].strip()

        if not section_text:
            continue

        # If section is too long, sub-chunk it
        words = section_text.split()
        if len(words) > max_chunk_size:
            sub_chunks = _split_long_section(section_text, title, max_chunk_size, min_chunk_size)
            for sc in sub_chunks:
                sc.page_numbers = _find_pages(sc.text, page_texts)
                chunks.append(sc)
        elif len(words) >= min_chunk_size:
            chunk = Chunk(
                text=section_text,
                section_title=title,
                page_numbers=_find_pages(section_text, page_texts),
                char_start=start,
                char_end=end,
            )
            chunks.append(chunk)

    return chunks


def _split_long_section(
    text: str, title: str, max_size: int, min_size: int
) -> list[Chunk]:
    """Split a long section into sub-chunks by paragraphs."""
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    current_text = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        combined = (current_text + "\n\n" + para).strip() if current_text else para

        if len(combined.split()) > max_size and current_text:
            chunks.append(Chunk(text=current_text, section_title=title))
            current_text = para
        else:
            current_text = combined

    if current_text and len(current_text.split()) >= min_size:
        chunks.append(Chunk(text=current_text, section_title=title))
    elif current_text and chunks:
        # Merge tiny remainder with previous chunk
        chunks[-1].text += "\n\n" + current_text

    return chunks


def _sliding_window_chunking(
    full_text: str,
    page_texts: dict[int, str],
    chunk_size: int = 300,
    overlap: int = 50,
) -> list[Chunk]:
    """Fallback: sliding window chunking (enhanced from original app.py)."""
    words = full_text.split()
    chunks = []
    i = 0

    while i < len(words):
        chunk_words = words[i : i + chunk_size]
        chunk_text = " ".join(chunk_words)
        page_nums = _find_pages(chunk_text, page_texts)

        chunks.append(Chunk(
            text=chunk_text,
            page_numbers=page_nums,
            char_start=i,
            char_end=i + len(chunk_words),
        ))
        i += chunk_size - overlap

    return chunks


def _find_pages(text: str, page_texts: dict[int, str]) -> list[int]:
    """Find which pages a chunk of text came from."""
    pages = []
    # Use first 60 chars as a fingerprint for matching
    snippet = text[:60].strip()
    if not snippet:
        return [1]

    for page_num, page_text in page_texts.items():
        if snippet in page_text or any(
            word in page_text for word in snippet.split()[:5]
        ):
            pages.append(page_num)
            if len(pages) >= 3:
                break

    return pages if pages else [1]


def _classify_chunk(text: str) -> str:
    """Classify a chunk by its content type."""
    scores = {}
    for ctype, pattern in TYPE_PATTERNS.items():
        matches = re.findall(pattern, text)
        scores[ctype] = len(matches)

    if not scores or max(scores.values()) == 0:
        return "general"

    return max(scores, key=scores.get)
