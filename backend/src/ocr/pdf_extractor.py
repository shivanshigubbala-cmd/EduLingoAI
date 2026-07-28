"""
PDF text extraction for P2-SHR3.

Extracts text from a PDF while preserving page boundaries.
"""

from pathlib import Path

import fitz  # PyMuPDF


class PDFExtractionError(Exception):
    """Raised when PDF text extraction fails."""


def extract_pdf_text(file_path: str | Path) -> list[dict]:
    """
    Extract text from a PDF page by page.

    Args:
        file_path: Path to the PDF file.

    Returns:
        A list of dictionaries, one per page:

        [
            {
                "page_number": 1,
                "text": "Text from page 1..."
            },
            {
                "page_number": 2,
                "text": "Text from page 2..."
            }
        ]

    Raises:
        PDFExtractionError: If the file does not exist,
                            cannot be opened, or contains no text.
    """

    path = Path(file_path)

    if not path.exists():
        raise PDFExtractionError(
            f"PDF file not found: {path}"
        )

    if not path.is_file():
        raise PDFExtractionError(
            f"Path is not a file: {path}"
        )

    try:
        document = fitz.open(path)

        pages = []

        for page_index, page in enumerate(document):
            text = page.get_text("text").strip()

            pages.append(
                {
                    "page_number": page_index + 1,
                    "text": text,
                }
            )

        document.close()

    except Exception as exc:
        raise PDFExtractionError(
            f"Failed to extract text from PDF: {exc}"
        ) from exc

    if not pages:
        raise PDFExtractionError(
            "The PDF contains no pages."
        )

    if not any(page["text"] for page in pages):
        raise PDFExtractionError(
            "No extractable text was found in the PDF."
        )

    return pages


def extract_pdf_text_as_string(file_path: str | Path) -> str:
    """
    Extract PDF text as a single string while preserving
    page boundaries.

    Page markers are included so downstream processing can
    identify the original page number.
    """

    pages = extract_pdf_text(file_path)

    return "\n\n".join(
        f"--- Page {page['page_number']} ---\n{page['text']}"
        for page in pages
    )