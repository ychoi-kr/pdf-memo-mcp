from typing import List, Dict

# --- Coordinate helpers ---

def pypdf_to_plumber_y(page_height: float, y_pdf: float) -> float:
    """Convert PDF user-space Y (origin bottom-left, y up) to
    pdfplumber Y (origin top-left, y down)."""
    return float(page_height) - float(y_pdf)


def union_boxes(boxes: List[List[float]]) -> List[float]:
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    return [x0, y0, x1, y1]


# --- Text extraction within bbox ---

def _intersects(bbox, w) -> bool:
    x0, top, x1, bottom = bbox
    return not (w["x1"] <= x0 or w["x0"] >= x1 or w["bottom"] <= top or w["top"] >= bottom)


def _words_in_bbox(bbox: List[float], words: List[Dict]) -> List[Dict]:
    return [w for w in words if _intersects(bbox, w)]


def _text_from_words_grouped(bbox: List[float], words: List[Dict], line_tol: float = 3.0) -> str:
    inside = _words_in_bbox(bbox, words)
    if not inside:
        return ""
    inside.sort(key=lambda w: (w["top"], w["x0"]))
    lines: List[List[Dict]] = []
    for w in inside:
        if not lines:
            lines.append([w])
            continue
        last = lines[-1]
        if abs(w["top"] - last[-1]["top"]) <= line_tol:
            last.append(w)
        else:
            lines.append([w])
    line_texts = [" ".join(w["text"] for w in line) for line in lines]
    return " ".join(t.strip() for t in line_texts if t.strip())


def extract_text_from_bbox(pl_page, bbox: List[float]) -> str:
    """Best-effort text extraction from a pdfplumber page area.
    1) Try page.within_bbox + extract_text (pdfminer layout order)
    2) Fallback to word grouping (y, then x) with line tolerance
    """
    pad = 1.0
    x0 = max(float(bbox[0]) - pad, 0)
    top = max(float(bbox[1]) - pad, 0)
    x1 = float(bbox[2]) + pad
    bottom = float(bbox[3]) + pad
    try:
        cropped = pl_page.within_bbox((x0, top, x1, bottom))
        text = cropped.extract_text()
        if text:
            return " ".join(s.strip() for s in text.splitlines() if s.strip())
    except Exception:
        pass
    words = pl_page.extract_words() or []
    return _text_from_words_grouped([x0, top, x1, bottom], words)
