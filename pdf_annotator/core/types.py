from typing import TypedDict, List, Optional

class Annotation(TypedDict, total=False):
    page: int
    type: str            # "/Highlight", "/Text"(sticky), etc.
    content: str
    author: str
    position: List[float]  # [x0, top, x1, bottom] in pdfplumber coordinates

class HighlightContext(TypedDict, total=False):
    page: int
    author: str
    highlighted_text: str
    note: str
    position: List[float]   # [x0, top, x1, bottom]
