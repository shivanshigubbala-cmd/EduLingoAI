"""Tests for P2-SHR4 — handwriting OCR.

Mocks the OCR.space API so tests are fast, deterministic, and don't depend
on network access or a real API key during CI.
"""
from unittest.mock import patch, MagicMock

import pytest

from src.ocr.handwriting_ocr import transcribe_handwriting, OCRError


def _mock_response(json_data, status_code=200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    return mock_resp


@patch("src.ocr.handwriting_ocr.requests.post")
def test_transcribe_handwriting_returns_text_and_confidence(mock_post, tmp_path):
    fake_image = tmp_path / "note.jpg"
    fake_image.write_bytes(b"fake image bytes")

    mock_post.return_value = _mock_response({
        "IsErroredOnProcessing": False,
        "ParsedResults": [{
            "ParsedText": "Hello world",
            "TextOverlay": {
                "Lines": [{
                    "Words": [
                        {"WordText": "Hello", "WordConfidence": 90},
                        {"WordText": "world", "WordConfidence": 88},
                    ]
                }]
            },
        }],
    })

    result = transcribe_handwriting(str(fake_image), "fake_api_key")

    assert result["text"] == "Hello world"
    assert result["confidence"] == pytest.approx(0.89, abs=0.01)
    assert result["confidence_flag"] is False


@patch("src.ocr.handwriting_ocr.requests.post")
def test_low_confidence_sets_flag(mock_post, tmp_path):
    fake_image = tmp_path / "note.jpg"
    fake_image.write_bytes(b"fake image bytes")

    mock_post.return_value = _mock_response({
        "IsErroredOnProcessing": False,
        "ParsedResults": [{
            "ParsedText": "Hello world",
            "TextOverlay": {
                "Lines": [{
                    "Words": [
                        {"WordText": "Hello", "WordConfidence": 40},
                        {"WordText": "world", "WordConfidence": 35},
                    ]
                }]
            },
        }],
    })

    result = transcribe_handwriting(str(fake_image), "fake_api_key")

    assert result["confidence"] < 0.65
    assert result["confidence_flag"] is True


@patch("src.ocr.handwriting_ocr.requests.post")
def test_no_text_raises_ocr_error(mock_post, tmp_path):
    fake_image = tmp_path / "note.jpg"
    fake_image.write_bytes(b"fake image bytes")

    mock_post.return_value = _mock_response({
        "IsErroredOnProcessing": False,
        "ParsedResults": [{"ParsedText": "", "TextOverlay": {}}],
    })

    with pytest.raises(OCRError, match="No text could be transcribed"):
        transcribe_handwriting(str(fake_image), "fake_api_key")


@patch("src.ocr.handwriting_ocr.requests.post")
def test_api_processing_error_raises_ocr_error(mock_post, tmp_path):
    fake_image = tmp_path / "note.jpg"
    fake_image.write_bytes(b"fake image bytes")

    mock_post.return_value = _mock_response({
        "IsErroredOnProcessing": True,
        "ErrorMessage": ["Unsupported image format"],
    })

    with pytest.raises(OCRError, match="OCR processing failed"):
        transcribe_handwriting(str(fake_image), "fake_api_key")


@patch("src.ocr.handwriting_ocr.requests.post")
def test_non_200_status_raises_ocr_error(mock_post, tmp_path):
    fake_image = tmp_path / "note.jpg"
    fake_image.write_bytes(b"fake image bytes")

    mock_post.return_value = _mock_response({}, status_code=500)

    with pytest.raises(OCRError, match="status 500"):
        transcribe_handwriting(str(fake_image), "fake_api_key")


def test_missing_file_raises_before_network_call():
    with pytest.raises(OCRError):
        transcribe_handwriting("does_not_exist.jpg", "fake_api_key")