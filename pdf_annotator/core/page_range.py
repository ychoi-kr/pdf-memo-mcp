from typing import List, Optional

def parse_page_range(total_pages: int, page_range: Optional[str]) -> List[int]:
    """Return zero-based page indices according to the flexible spec.
    Supports: None(all), "first", "last", "N", "S-E".
    """
    if total_pages <= 0:
        return []
    if page_range is None:
        return list(range(total_pages))

    pr = str(page_range).strip().lower()
    if pr == "first":
        return [0]
    if pr == "last":
        return [total_pages - 1]
    if "-" in pr:
        s, e = pr.split("-", 1)
        s_i = int(s) if s else 1
        e_i = int(e) if e else total_pages
        if s_i < 1 or e_i < 1 or s_i > total_pages:
            raise ValueError(f"Invalid page range: {page_range}")
        return list(range(s_i - 1, min(e_i, total_pages)))
    # single page number
    p = int(pr)
    if p < 1 or p > total_pages:
        raise ValueError(f"Page {p} out of range (1-{total_pages})")
    return [p - 1]
