"""PDF text extraction module.

Reuses pdfplumber from the original codebase, enhanced with:
- Page-level text tracking (for source citations)
- Metadata extraction
- Scanned PDF detection
"""

import pdfplumber
from pathlib import Path
from dataclasses import dataclass, field
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class PageText:
    """Text content from a single PDF page."""
    page_number: int
    text: str
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.text)


@dataclass
class ParsedDocument:
    """Complete parsed PDF document."""
    filename: str
    pages: list[PageText] = field(default_factory=list)
    total_pages: int = 0
    total_chars: int = 0
    is_scanned: bool = False
    metadata: dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text)


def parse_pdf(file_path: str | Path) -> ParsedDocument:
    """Extract text from a PDF file with page-level tracking.

    Args:
        file_path: Path to the PDF file.

    Returns:
        ParsedDocument with page-level text and metadata.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    pages: list[PageText] = []
    metadata = {}

    try:
        with pdfplumber.open(str(file_path)) as pdf:
            metadata = pdf.metadata or {}

            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                # Clean up common PDF artifacts
                text = _clean_text(text)
                pages.append(PageText(page_number=i + 1, text=text))

    except Exception as e:
        logger.error(f"Failed to parse PDF {file_path}: {e}")
        raise ValueError(f"Could not parse PDF: {e}")

    total_chars = sum(p.char_count for p in pages)
    non_empty_pages = sum(1 for p in pages if p.char_count > 50)

    # Detect likely scanned PDFs (very little text extracted)
    is_scanned = len(pages) > 0 and (non_empty_pages / len(pages)) < 0.3

    if is_scanned:
        logger.warning(f"PDF {file_path.name} appears to be scanned ({non_empty_pages}/{len(pages)} pages have text)")

    doc = ParsedDocument(
        filename=file_path.name,
        pages=pages,
        total_pages=len(pages),
        total_chars=total_chars,
        is_scanned=is_scanned,
        metadata=metadata,
    )

    logger.info(f"Parsed {file_path.name}: {doc.total_pages} pages, {doc.total_chars} chars")
    return doc


def _clean_text(text: str) -> str:
    """Clean extracted PDF text."""
    # Remove excessive whitespace but preserve paragraph breaks
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove common PDF artifacts
    text = re.sub(r'\x00', '', text)
    text = text.strip()
    return text
