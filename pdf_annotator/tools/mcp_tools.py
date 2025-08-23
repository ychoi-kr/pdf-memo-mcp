import json
import logging
from typing import Optional, Set

from mcp.server.fastmcp import FastMCP

from pdf_annotator.core import paths as _paths
from pdf_annotator.core.paths import (
    find_file,
    list_pdf_files_text,
    MAX_FILE_SIZE,
    ALLOWED_EXTENSIONS,
)
from pdf_annotator.core.page_range import parse_page_range
from pdf_annotator.backends.pypdf2_backend import extract_annotations as backend_extract_annotations
from pdf_annotator.backends.pdfplumber_backend import extract_highlights_with_context as backend_extract_highlights

import pdfplumber

logger = logging.getLogger(__name__)

mcp = FastMCP("PDF Annotator")


# ---------- Explicit tools ----------
@mcp.tool()
async def extract_annotations(
    file_path: str,
    page_range: Optional[str] = None,
    include_types: str = "Highlight,Text",
    drop_empty: bool = True,
) -> str:
    """Extract annotations from a PDF.

    Parameters
    ----------
    file_path: str
        Filename (relative) or absolute path to the PDF. The file must reside within the configured accessible directories.
    page_range: Optional[str]
        Flexible spec: `first`, `last`, `N`, `S-E`, or `None` for all pages.
    include_types: str
        Comma-separated set of annotation types to include (case-insensitive; leading `/` ignored),
        e.g. "Highlight,Text". By default, excludes noisy types such as Link/Popup.
    drop_empty: bool
        If True, drops annotations with both `author` and `content` empty.
    """
    path = find_file(file_path)
    if not path:
        return (
            "Error: Could not find file '{file}'. Provide an absolute path or place the file within the configured accessible directories."
        ).format(file=file_path)

    types: Set[str] = {t.strip().lstrip("/").lower() for t in include_types.split(",") if t.strip()}
    items = backend_extract_annotations(path, page_range, types, drop_empty)
    result = {
        "file_name": path.name,
        "path": str(path),
        "page_range": page_range or "all",
        "total_annotations": len(items),
        "annotations": items,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def extract_highlights_with_context(
    file_path: str,
    page_range: Optional[str] = None,
    drop_empty: bool = True,
) -> str:
    """Map **highlight annotations** to their underlying text."""
    path = find_file(file_path)
    if not path:
        return f"Error: Could not find file '{file_path}'."

    items = backend_extract_highlights(path, page_range, drop_empty)
    if not items:
        scope = page_range or "all"
        return f"No highlights (with text) found in '{path.name}' (scope: {scope})."
    return json.dumps(items, indent=2, ensure_ascii=False)


# ---------- Backward-compatible wrappers ----------
@mcp.tool()
async def extract_pdf_annotations(
    file_path: str,
    page_range: Optional[str] = None,
    drop_empty: bool = True,
) -> str:
    """Compatibility wrapper for annotation extraction.

    Equivalent to `extract_annotations(..., include_types="Highlight,Text", drop_empty=True)`.
    """
    return await extract_annotations(
        file_path=file_path,
        page_range=page_range,
        include_types="Highlight,Text",
        drop_empty=drop_empty,
    )


@mcp.tool()
async def extract_annotations_with_context(
    file_path: str,
    page_range: Optional[str] = None,
    drop_empty: bool = True,
) -> str:
    """Compatibility wrapper for highlight mapping."""
    return await extract_highlights_with_context(
        file_path=file_path, page_range=page_range, drop_empty=drop_empty
    )


# ---------- Other tools ----------
@mcp.tool()
async def read_pdf_text(file_path: str, page_range: Optional[str] = None) -> str:
    """Extract page text and basic PDF metadata.

    Returns JSON with: file_name, total_pages, page_range, extracted_pages[{page_number, text, char_count}], metadata.
    """
    path = find_file(file_path)
    if not path:
        return f"Error: Could not find file '{file_path}'."
    try:
        with pdfplumber.open(path) as pdf:
            total = len(pdf.pages)
            idxs = parse_page_range(total, page_range)
            pages = []
            for i in idxs:
                page = pdf.pages[i]
                text = (page.extract_text() or "").strip()
                pages.append({"page_number": i + 1, "text": text, "char_count": len(text)})
            md = pdf.metadata or {}
            result = {
                "file_name": path.name,
                "total_pages": total,
                "page_range": page_range or "all",
                "extracted_pages": pages,
                "metadata": {
                    "title": md.get("Title", ""),
                    "author": md.get("Author", ""),
                    "subject": md.get("Subject", ""),
                    "creator": md.get("Creator", ""),
                    "producer": md.get("Producer", ""),
                    "creation_date": str(md.get("CreationDate", "")),
                    "mod_date": str(md.get("ModDate", "")),
                },
            }
            return json.dumps(result, indent=2, ensure_ascii=False)
    except ValueError as ve:
        return f"Error: {ve}"
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        return f"Error: {e}"


@mcp.tool()
async def list_pdf_files(directory: str = "all", depth: int = 0, limit: int = 50) -> str:
    """
    List PDFs under the configured directories.

    Parameters
    ----------
    directory : str, default "all"
        "all" → scan every allowed root (many MCP hosts send this by default).
        Otherwise, this is a substring filter applied to each allowed root:
        - First, it matches the root's basename (e.g., "Temp" for "C:\\Temp").
        - If not matched, it checks if the string is contained in the absolute path.
        If multiple roots match, all of them are scanned.

        Examples:
        - "Temp"   → only roots whose basename contains "Temp" (e.g., C:\\Temp)
        - "C:\\Temp" → the C:\\Temp root specifically (if configured)
        - "all"    → every configured root

    depth : int, default 0
        0 = only the root (non-recursive). 1 = include one subdirectory level, etc.
        The server clamps depth internally for safety (currently max = 5).
    
    limit: int, default 50
        Maximum number of files to display **per matched root** (most recent first).
        Clamped internally (e.g., 1..200) for safety.
    
    Returns
    -------
    str
        Human-readable summary. Shows up to 15 most-recent PDFs per matched root.
        Use `show_accessible_directories()` to see which roots can be matched.

    Notes
    -----
    - If your MCP host calls this tool with directory="all", you’ll see every root.
      To focus on a single root (e.g., C:\\Temp), pass a distinctive filter like "Temp"
      or "C:\\\\Temp".
    - This tool is read-only and respects allowed directory, file size, and extension checks.
    """
    return list_pdf_files_text(directory, depth, limit)


@mcp.tool()
async def show_accessible_directories() -> str:
    """Return the current directory/configuration constraints as JSON."""
    info = {
        "accessible_directories": _paths.SEARCH_DIRECTORIES,
        "directory_count": len(_paths.SEARCH_DIRECTORIES),
        "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
        "allowed_extensions": ALLOWED_EXTENSIONS,
    }
    return json.dumps(info, indent=2, ensure_ascii=False)
