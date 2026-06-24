"""Handwriting OCR — EasyOCR + TrOCR for handwritten date/signature extraction.
Lazy-loaded models (only imported on first use)."""
import re
from collections import Counter


# Lazy-loaded model references
_easyocr_reader = None
_trocr_processor = None
_trocr_model = None


def _get_easyocr():
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        _easyocr_reader = easyocr.Reader(["en"], gpu=False)
    return _easyocr_reader


def _get_trocr():
    global _trocr_processor, _trocr_model
    if _trocr_model is None:
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        _trocr_processor = TrOCRProcessor.from_pretrained("microsoft/trocr-large-handwritten")
        _trocr_model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-large-handwritten")
    return _trocr_processor, _trocr_model


def _clean_digit(text):
    """Convert letter O to digit 0, I to 1, etc."""
    mapping = {"O": "0", "I": "1", "l": "1", "S": "5", "B": "8"}
    result = []
    for ch in text:
        if ch in mapping:
            result.append(mapping[ch])
        else:
            result.append(ch)
    return "".join(result)


def extract_text(image):
    """Extract text from image using EasyOCR (primary) with fallback."""
    reader = _get_easyocr()
    results = reader.readtext(image)
    return " ".join([r[1] for r in results])


def _to_native(obj):
    """Recursively convert numpy types to native Python types."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_to_native(i) for i in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return _to_native(obj.tolist())
    return obj

def has_signature_zone(image):
    """Detect signature zone presence using EasyOCR and image analysis.
    Returns dict with 'has_signature' bool and optional 'locations' list."""
    reader = _get_easyocr()
    results = reader.readtext(image)
    text = " ".join([r[1] for r in results]).upper()
    keywords = ["SIGNATURE", "SIGNED", "SIGN", "AUTHORIZED", "APPROVED BY",
                "PREPARED BY", "VERIFIED BY", "DATE:", "ANAK", "BIN ", "BINTI"]
    locations = []

    # Text-based detections
    for r in results:
        txt = r[1].upper()
        conf = r[2]
        bbox = r[0]
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        for kw in keywords:
            if kw in txt:
                locations.append({
                    "type": "text",
                    "label": kw,
                    "bbox": [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))],
                    "confidence": float(conf),
                })
                break

    # Image-based: find ink regions (handwritten strokes)
    import cv2, numpy as np
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    sig_regions = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = int(cw) * int(ch)
        aspect = int(cw) / max(int(ch), 1)
        if 50 < int(cw) < 600 and 15 < int(ch) < 250 and area > 500 and 0.5 < aspect < 8.0:
            sig_regions.append({"bbox": [int(x), int(y), int(x) + int(cw), int(y) + int(ch)], "area": area})
    sig_regions.sort(key=lambda r: r["area"], reverse=True)

    has_sig = len(locations) > 0 or len(sig_regions) > 0
    return _to_native({
        "has_signature": has_sig,
        "locations": locations + sig_regions[:3],
    })


def extract_handwritten_dates(image):
    """Extract handwritten dates from an image region.
    Returns list of date strings found.
    """
    import cv2
    import numpy as np
    reader = _get_easyocr()

    # Try full-page OCR first
    results = reader.readtext(image)
    dates = _parse_dates_from_text(" ".join([r[1] for r in results]))

    if dates:
        return dates

    # Crop-based fallback with adaptive threshold
    h, w = image.shape[:2]
    crop = image[max(0, h//3):h, 0:w]

    # Adaptive threshold to bring out faint ink
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 11, 2)
    enhanced = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

    # Multi-pass majority voting (3 passes)
    all_detections = []
    for _ in range(3):
        pass_results = reader.readtext(enhanced)
        for r2 in pass_results:
            if r2[2] >= 0.05:
                cleaned = _clean_digit(r2[1])
                all_detections.append(cleaned)

    # Majority vote
    if all_detections:
        text_votes = Counter(all_detections)
        final_text = text_votes.most_common(1)[0][0]
        dates = _parse_dates_from_text(final_text)

    # Year padding fallback
    if not dates:
        combined = " ".join(all_detections)
        date_pattern = re.findall(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', combined)
        for dp in date_pattern:
            parts = re.split(r'[/-]', dp)
            if len(parts[2]) == 2:
                y = "20" + parts[2] if int(parts[2]) < 50 else "19" + parts[2]
                parts[2] = y
            dates.append("/".join(parts))

    return dates


def _parse_dates_from_text(text):
    """Parse date patterns like DD/MM/YYYY or DD-MM-YYYY from text."""
    dates = []
    patterns = [
        r'(\d{2}[/-]\d{2}[/-]\d{4})',
        r'(\d{1}[/-]\d{2}[/-]\d{4})',
        r'(\d{2}[/-]\d{1}[/-]\d{4})',
    ]
    for pat in patterns:
        matches = re.findall(pat, text)
        for m in matches:
            # Basic validation
            parts = re.split(r'[/-]', m)
            try:
                d, mo, y = int(parts[0]), int(parts[1]), int(parts[2])
                if 1 <= d <= 31 and 1 <= mo <= 12 and 2000 <= y <= 2100:
                    dates.append(m)
            except ValueError:
                continue
    return dates
