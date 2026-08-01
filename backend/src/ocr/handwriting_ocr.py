"""Handwriting OCR for P2-SHR4.

Transcribes handwritten notes (png/jpg) using the OCR.space API — chosen
over a local model (Tesseract/Ollama+llava) since it needs no local
install or disk space, and over Claude Vision to avoid per-call API costs
during development.

Low-confidence transcriptions are flagged so the student can review/correct
before the topic tree is built on top of possibly-wrong text.
"""
import requests

OCR_SPACE_URL = "https://api.ocr.space/parse/image"

# Below this, we flag the result for the student to review rather than
# silently feeding possibly-garbled text into the topic tree.
LOW_CONFIDENCE_THRESHOLD = 0.65


class OCRError(Exception):
    """Raised when handwriting OCR fails or returns no usable text."""


def transcribe_handwriting(file_path: str, api_key: str) -> dict:
    """Transcribe a handwritten image via the OCR.space API.

    Args:
        file_path: Path to the image file (png/jpg).
        api_key: OCR.space API key.

    Returns:
        {
            "text": "transcribed text...",
            "confidence": 0.82,           # 0-1 scale
            "confidence_flag": False,     # True if below threshold
        }

    Raises:
        OCRError: If the request fails or no text is returned.
    """
    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                OCR_SPACE_URL,
                files={"file": f},
                data={
                    "apikey": api_key,
                    "OCREngine": 2,  # engine 2 handles handwriting better
                    "scale": True,
                    "detectOrientation": True,
                },
                timeout=30,
            )
    except OSError as exc:
        # Covers missing file, permission errors, etc. — surfaced as OCRError
        # so callers only ever need to catch one exception type from this
        # module, rather than OCRError for API issues and OSError for local
        # file issues.
        raise OCRError(f"Could not read image file '{file_path}': {exc}") from exc
    except requests.RequestException as exc:
        raise OCRError(f"OCR request failed: {exc}") from exc

    if response.status_code != 200:
        raise OCRError(f"OCR API returned status {response.status_code}")

    result = response.json()

    if result.get("IsErroredOnProcessing"):
        error_msg = result.get("ErrorMessage", ["Unknown OCR error"])
        raise OCRError(f"OCR processing failed: {error_msg}")

    parsed_results = result.get("ParsedResults")
    if not parsed_results:
        raise OCRError("OCR returned no results.")

    text = parsed_results[0].get("ParsedText", "").strip()
    if not text:
        raise OCRError("No text could be transcribed from this image.")

    # OCR.space's free tier doesn't return a numeric confidence score, so we
    # derive a simple heuristic from the engine's own per-line confidence
    # when available, falling back to a text-quality proxy otherwise.
    confidence = _estimate_confidence(parsed_results[0], text)

    return {
        "text": text,
        "confidence": confidence,
        "confidence_flag": confidence < LOW_CONFIDENCE_THRESHOLD,
    }


def _estimate_confidence(parsed_result: dict, text: str) -> float:
    """Estimate transcription confidence on a 0-1 scale.

    Uses OCR.space's TextOverlay line-level data when present; otherwise
    falls back to a rough heuristic based on recognized-word density
    (e.g. lots of single-character "words" or symbols suggests a garbled
    read rather than clean handwriting).
    """
    overlay = parsed_result.get("TextOverlay", {})
    lines = overlay.get("Lines", [])
    if lines:
        word_confidences = [
            word.get("WordConfidence", 0) / 100
            for line in lines
            for word in line.get("Words", [])
            if "WordConfidence" in word
        ]
        if word_confidences:
            return sum(word_confidences) / len(word_confidences)

    words = text.split()
    if not words:
        return 0.0
    short_or_symbolic = sum(1 for w in words if len(w) <= 1 or not w.isalnum())
    noise_ratio = short_or_symbolic / len(words)
    return max(0.0, min(1.0, 1.0 - noise_ratio))