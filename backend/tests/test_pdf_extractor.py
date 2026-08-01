from pathlib import Path

import fitz
import pytest

from src.ocr.pdf_extractor import (
    PDFExtractionError,
    extract_pdf_text,
    extract_pdf_text_as_string,
)


def create_test_pdf(tmp_path: Path, pages: list[str]) -> Path:
    """Create a simple text PDF for testing."""
    pdf_path = tmp_path / "test.pdf"

    document = fitz.open()

    for text in pages:
        page = document.new_page()
        page.insert_text((72, 72), text)

    document.save(pdf_path)
    document.close()

    return pdf_path


def test_extract_pdf_text_preserves_page_numbers(tmp_path):
    pdf_path = create_test_pdf(
        tmp_path,
        [
            "This is page one.",
            "This is page two.",
            "This is page three.",
        ],
    )

    result = extract_pdf_text(pdf_path)

    assert len(result) == 3
    assert result[0]["page_number"] == 1
    assert result[1]["page_number"] == 2
    assert result[2]["page_number"] == 3

    assert "page one" in result[0]["text"]
    assert "page two" in result[1]["text"]
    assert "page three" in result[2]["text"]


def test_extract_pdf_text_as_string_preserves_page_markers(tmp_path):
    pdf_path = create_test_pdf(
        tmp_path,
        [
            "First page content.",
            "Second page content.",
        ],
    )

    result = extract_pdf_text_as_string(pdf_path)

    assert "--- Page 1 ---" in result
    assert "--- Page 2 ---" in result
    assert "First page content." in result
    assert "Second page content." in result


def test_extract_pdf_text_raises_for_missing_file(tmp_path):
    missing_file = tmp_path / "missing.pdf"

    with pytest.raises(PDFExtractionError):
        extract_pdf_text(missing_file)


def test_extract_pdf_text_raises_for_blank_pdf(tmp_path):
    pdf_path = tmp_path / "blank.pdf"

    document = fitz.open()
    document.new_page()
    document.save(pdf_path)
    document.close()

    with pytest.raises(PDFExtractionError):
        extract_pdf_text(pdf_path)