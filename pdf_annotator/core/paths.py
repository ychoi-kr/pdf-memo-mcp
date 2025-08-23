import argparse
import logging
import os
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Limits and filters
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = [".pdf"]

# Default search directories (used when no args are provided)
DEFAULT_SEARCH_DIRECTORIES = [
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.getcwd(),
]

# Actual configured directories (initialized at runtime)
SEARCH_DIRECTORIES: List[str] = []


def parse_arguments():
    """Parse CLI arguments to configure accessible directories and limits."""
    parser = argparse.ArgumentParser(
        description="PDF Annotator MCP Server — configurable directories and text reading",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "\nExamples:\n"
            "  python main.py ~/Downloads ~/Documents\n"
            "  python main.py --allow-dir ~/Work --allow-dir /shared/pdfs\n"
            "  python main.py ~/Downloads --max-file-size 52428800 --log-level DEBUG\n"
        ),
    )

    # 1) Positional directories
    parser.add_argument(
        "directories",
        nargs="*",
        help="Accessible directories for PDFs (space-separated)",
    )

    # 2) Repeated --allow-dir option
    parser.add_argument(
        "--allow-dir",
        action="append",
        dest="allowed_dirs",
        help="Add an allowed directory (can be used multiple times)",
    )

    parser.add_argument(
        "--max-file-size",
        type=int,
        default=100 * 1024 * 1024,
        help="Maximum file size in bytes (default: 100MB)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    return parser.parse_args()


def _is_within(base: str, target: str) -> bool:
    base = os.path.join(os.path.realpath(base), "")  # ensure trailing separator
    target = os.path.realpath(target)
    return target.startswith(base) or target == base[:-1]


def setup_search_directories(args) -> None:
    """Configure SEARCH_DIRECTORIES and MAX_FILE_SIZE from parsed args.
    Falls back to DEFAULT_SEARCH_DIRECTORIES for backward compatibility when none provided.
    """
    global SEARCH_DIRECTORIES, MAX_FILE_SIZE

    MAX_FILE_SIZE = int(args.max_file_size)

    provided: List[str] = []
    if getattr(args, "directories", None):
        provided.extend(args.directories)
    if getattr(args, "allowed_dirs", None):
        provided.extend(args.allowed_dirs)

    # No directories provided → use defaults
    if not provided:
        SEARCH_DIRECTORIES = [
            os.path.realpath(os.path.abspath(os.path.expanduser(d))) for d in DEFAULT_SEARCH_DIRECTORIES
        ]
        logger.info("Using default search directories (backward compatible).")
        return

    validated: List[str] = []
    for d in provided:
        try:
            expanded = os.path.expanduser(d)
            abs_path = os.path.abspath(expanded)
            real_path = os.path.realpath(abs_path)
            if not os.path.exists(real_path):
                logger.info(f"Creating directory: {real_path}")
                os.makedirs(real_path, exist_ok=True)
            if not os.path.isdir(real_path):
                logger.warning(f"Not a directory, skipped: {d} -> {real_path}")
                continue
            if not os.access(real_path, os.R_OK):
                logger.warning(f"Unreadable directory, skipped: {d} -> {real_path}")
                continue
            validated.append(real_path)
        except Exception as e:
            logger.error(f"Failed to process directory '{d}': {e}")

    if not validated:
        logger.warning("No valid directories from arguments; falling back to defaults.")
        validated = [os.path.realpath(os.path.abspath(os.path.expanduser(d))) for d in DEFAULT_SEARCH_DIRECTORIES]
    
    # IMPORTANT: mutate in place so other modules see the update
    SEARCH_DIRECTORIES.clear()
    SEARCH_DIRECTORIES.extend(validated)


def validate_and_resolve_path(file_path: str) -> Optional[Path]:
    """Validate a candidate file path and return an absolute Path if allowed and safe."""
    try:
        abs_path = os.path.expanduser(file_path) if file_path.startswith("~") else os.path.abspath(file_path)
        real_path = os.path.realpath(abs_path)

        # Must be within one of the allowed directories; block traversal
        is_safe = any(_is_within(allowed, real_path) for allowed in SEARCH_DIRECTORIES)
        if not is_safe or ".." in Path(file_path).parts:
            logger.warning(f"Security risk detected (outside allowed directories): {file_path}")
            return None

        resolved = Path(real_path)
        if not resolved.is_file():
            return None
        if resolved.suffix.lower() not in ALLOWED_EXTENSIONS:
            logger.warning(f"Disallowed file extension: {file_path}")
            return None
        if resolved.stat().st_size > MAX_FILE_SIZE:
            logger.warning(f"File too large: {file_path}")
            return None
        return resolved
    except Exception as e:
        logger.error(f"Error validating path {file_path}: {e}")
        return None


def find_file(file_name: str) -> Optional[Path]:
    """Resolve an absolute path or search by name/substring within the configured directories."""
    # Absolute or ~ path
    if os.path.isabs(file_name) or file_name.startswith("~"):
        path = validate_and_resolve_path(file_name)
        if path and path.exists():
            return path

    # Search allowed directories
    for directory in SEARCH_DIRECTORIES:
        try:
            dir_path = Path(directory)
            # Direct match
            potential = dir_path / file_name
            path = validate_and_resolve_path(str(potential))
            if path and path.exists():
                return path
            # Fuzzy match
            for pdf in dir_path.glob("*.pdf"):
                if file_name.lower() in pdf.name.lower():
                    path = validate_and_resolve_path(str(pdf))
                    if path and path.exists():
                        return path
        except Exception as e:
            logger.error(f"Error searching directory {directory}: {e}")
            continue

    logger.warning(f"File not found: {file_name}")
    return None


def _gather_pdfs_under(root: str, depth: int):
    """Yield Path objects for PDFs under `root` up to `depth` levels (0 = only root)."""
    from pathlib import Path as _Path
    import os as _os

    root = _os.path.realpath(root)
    if depth <= 0:
        p = _Path(root)
        for f in p.glob("*.pdf"):
            if f.is_file():
                yield f
        return

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        rel = _os.path.relpath(dirpath, root)
        current_depth = 0 if rel == "." else rel.count(_os.sep) + 1
        if current_depth > depth:
            dirnames[:] = []  # stop descending further
            continue
        for fn in filenames:
            if fn.lower().endswith(".pdf"):
                fp = _os.path.join(dirpath, fn)
                f = _Path(fp)
                if f.is_file():
                    yield f


def _resolve_subdir_target(directory_filter: str) -> Optional[str]:
    """
    If `directory_filter` looks like a filesystem path, resolve/normalize it and
    return it only if it is a directory under any allowed root. Otherwise None.
    """
    try:
        looks_like_path = (os.path.isabs(directory_filter)
                           or os.sep in directory_filter
                           or (os.altsep and os.altsep in directory_filter))
        if not looks_like_path:
            return None

        cand = os.path.realpath(os.path.abspath(os.path.expanduser(directory_filter)))
        if not os.path.isdir(cand):
            return None

        # must be under one of the allowed roots
        for root in SEARCH_DIRECTORIES:
            if _is_within(root, cand):
                return cand
        return None
    except Exception:
        return None


def list_pdf_files_text(directory: str = "all", depth: int = 0, limit: int = 50) -> str:
    """
    Build the human-readable listing used by `list_pdf_files`.

    `directory` behaves as a substring filter on allowed roots
    (basename first, then absolute path). "all" scans every root.
    `depth` controls recursion (0 = root only), clamped for safety.
    """
    try:
        results: List[str] = []
        dirs = SEARCH_DIRECTORIES

        # Safety clamp for recursion depth (0 = only root; capped at 5)
        depth_clamped = max(0, min(int(depth), 5))
        # Safety clamp for per-root display count
        limit_clamped = max(1, min(int(limit), 200))

        if directory != "all":
            # 1) Path-like? Treat as a subdirectory request under an allowed root.
            subdir = _resolve_subdir_target(directory)
            if subdir:
                dirs = [subdir]  # scan only this subdirectory as the "root"
                heading_label = os.path.basename(subdir) or subdir
            else:
                # 2) Fallback: substring match on allowed roots
                filtered = [
                    d for d in SEARCH_DIRECTORIES
                    if directory.lower() in os.path.basename(d).lower() or directory in d
                ]
                dirs = filtered or []
                if not dirs:
                    return f"Error: No accessible directory matched '{directory}'."

        total = 0
        for d in dirs:
            p = Path(d)
            if not p.is_dir():
                continue
            files = list(_gather_pdfs_under(d, depth_clamped))
            files_sorted = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:limit_clamped]
            label = os.path.basename(d) or d
            results.append(
                f"[{label}] PDF files (depth={depth_clamped}; "
                f"showing up to {limit_clamped} most recent of {len(files)} total):"
            )
            for pdf in files_sorted:
                size_mb = pdf.stat().st_size / 1024**2
                # Show relative path from the root directory for better readability
                try:
                    relative_path = pdf.relative_to(d)
                    if str(relative_path) == pdf.name:
                        # File is directly in root directory, just show name
                        path_display = pdf.name
                    else:
                        # File is in subdirectory, show relative path
                        path_display = f"{relative_path} → {pdf.name}"
                except ValueError:
                    # Fallback to absolute path if relative_to fails
                    path_display = f"{pdf.name} → {str(pdf)}"
                
                results.append(f"- {path_display} ({size_mb:.1f} MB)")
            results.append("")
            total += len(files)

        if not results:
            return "No PDF files found in the accessible directories."

        header = [
            f"Directories scanned: {len(dirs)} of {len(SEARCH_DIRECTORIES)} configured",
            f"Approx. total PDFs: {total}",
            "=" * 40,
        ]
        return "\n".join(header + results)
    except Exception as e:
        logger.error(f"Error listing PDFs: {e}")
        return f"Error: {e}"
