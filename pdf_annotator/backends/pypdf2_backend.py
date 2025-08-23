from pathlib import Path
from typing import List, Optional, Set, Dict, Any
import logging
import PyPDF2

from pdf_annotator.core.page_range import parse_page_range
from pdf_annotator.core.types import Annotation

logger = logging.getLogger(__name__)


def _get_popup_contents(obj) -> str:
    try:
        if obj.get("/Popup") is not None:
            pop = obj.get("/Popup").get_object()
            return pop.get("/Contents", "") or ""
    except Exception:
        pass
    return ""


def extract_annotations(
    pdf_path: Path,
    page_range: Optional[str],
    include_types: Set[str],  # lowercased, without leading slash e.g., {"highlight","text"}
    drop_empty: bool = True,
) -> List[Annotation]:
    items: List[Annotation] = []
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            total = len(reader.pages)
            idxs = parse_page_range(total, page_range)

            for page_index in idxs:
                page = reader.pages[page_index]
                if "/Annots" not in page:
                    continue
                for annot in page["/Annots"]:
                    obj = annot.get_object()
                    subtype = str(obj.get("/Subtype", "")).lstrip("/").lower()
                    if include_types and subtype not in include_types:
                        continue

                    content = obj.get("/Contents", "") or obj.get("/RC", "") or _get_popup_contents(obj) or ""
                    author = obj.get("/T", "") or obj.get("/Title", "") or ""
                    rect = obj.get("/Rect", [])

                    item: Annotation = {
                        "page": page_index + 1,
                        "type": f"/{subtype.capitalize()}",
                        "content": str(content),
                        "author": str(author),
                        "position": [float(p) for p in rect] if rect else [],
                    }
                    if drop_empty and not item["content"] and not item["author"]:
                        continue
                    items.append(item)
    except Exception as e:
        logger.error(f"PyPDF2 extraction failed for {pdf_path}: {e}")
        raise
    return items
