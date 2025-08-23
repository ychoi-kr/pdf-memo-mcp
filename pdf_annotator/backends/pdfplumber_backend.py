from pathlib import Path
from typing import List, Optional
import logging
import PyPDF2
import pdfplumber

from pdf_annotator.core.page_range import parse_page_range
from pdf_annotator.core.types import HighlightContext
from pdf_annotator.core.bbox import pypdf_to_plumber_y, extract_text_from_bbox, union_boxes

logger = logging.getLogger(__name__)


def _note_from_obj(obj) -> str:
    note = obj.get("/Contents", "") or obj.get("/RC", "") or ""
    if not note and obj.get("/Popup") is not None:
        try:
            pop = obj.get("/Popup").get_object()
            note = pop.get("/Contents", "") or note
        except Exception:
            pass
    return note


def extract_highlights_with_context(
    pdf_path: Path,
    page_range: Optional[str],
    drop_empty: bool = True,
) -> List[HighlightContext]:
    out: List[HighlightContext] = []
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            with pdfplumber.open(pdf_path) as pdf:
                total = len(pdf.pages)
                idxs = parse_page_range(total, page_range)

                for page_index in idxs:
                    pypdf_page = reader.pages[page_index]
                    pl_page = pdf.pages[page_index]
                    page_h = float(getattr(pl_page, "height", pypdf_page.mediabox.top))

                    if "/Annots" not in pypdf_page:
                        continue

                    for annot in pypdf_page["/Annots"]:
                        obj = annot.get_object()
                        subtype = str(obj.get("/Subtype", "")).lstrip("/")
                        if subtype.lower() != "highlight":
                            continue

                        author = obj.get("/T", "") or obj.get("/Title", "") or ""
                        note = _note_from_obj(obj)

                        bboxes: List[List[float]] = []
                        quads = obj.get("/QuadPoints")
                        if isinstance(quads, list) and len(quads) >= 8:
                            for i in range(0, len(quads), 8):
                                xs = [float(quads[i]), float(quads[i+2]), float(quads[i+4]), float(quads[i+6])]
                                ys_pdf = [float(quads[i+1]), float(quads[i+3]), float(quads[i+5]), float(quads[i+7])]
                                ys_pl = [pypdf_to_plumber_y(page_h, y) for y in ys_pdf]
                                x0, x1 = min(xs), max(xs)
                                top, bottom = min(ys_pl), max(ys_pl)
                                bboxes.append([x0, top, x1, bottom])
                        else:
                            rect = obj.get("/Rect", [])
                            if rect and len(rect) >= 4:
                                x0 = float(min(rect[0], rect[2]))
                                x1 = float(max(rect[0], rect[2]))
                                y0 = float(min(rect[1], rect[3]))
                                y1 = float(max(rect[1], rect[3]))
                                top = pypdf_to_plumber_y(page_h, y1)
                                bottom = pypdf_to_plumber_y(page_h, y0)
                                bboxes.append([x0, top, x1, bottom])
                        if not bboxes:
                            continue

                        spans: List[str] = []
                        for bb in bboxes:
                            t = extract_text_from_bbox(pl_page, bb)
                            if t:
                                spans.append(t)
                        highlighted = " ".join(spans).strip()

                        union = union_boxes(bboxes)
                        item: HighlightContext = {
                            "page": page_index + 1,
                            "author": str(author),
                            "highlighted_text": highlighted,
                            "note": str(note),
                            "position": union,
                        }
                        if drop_empty and not item["highlighted_text"] and not item["note"]:
                            continue
                        out.append(item)
    except Exception as e:
        logger.error(f"pdfplumber highlight mapping failed for {pdf_path}: {e}")
        raise
    return out
