# PDF Memo MCP Server

A Model Context Protocol (MCP) server that lets Claude (or any MCP client) work with your PDFs safely. It can **list PDFs**, **extract highlights with their exact text**, **return raw notes/annotations**, **read specific pages**, and **show metadata**—all strictly limited to the directories you allow.

## Features

* **Annotation extraction**: parse PDF annotations with sensible filtering (e.g., include `Highlight, Text` by default; ignore noisy `Link/Popup` unless requested).
* **Highlight→text mapping**: map highlight quads/rects to the underlying page text.
* **Flexible page ranges**: `first`, `last`, `N`, `S-E`, or omit for all.
* **Metadata**: title, author, subject, creator/producer, creation/mod dates.
* **Configurable directories**: allow multiple roots via positional args or repeated `--allow-dir`.
* **Safety**: access limited to allowed directories, file size/extension checks.

## Requirements

* Python **3.10+** (3.11 recommended)
* `pip install -r requirements.txt`

```
PyPDF2>=3.0.0,<4
pdfplumber>=0.11.0,<0.12
mcp>=0.4.0
```

## Installation

```bash
# 1) Clone this repo
# Windows PowerShell / macOS / Linux
cd <your-workspace>
git clone <this-repo-url> pdf-memo-mcp
cd pdf-memo-mcp

# 2) (Optional) Create a virtualenv
python -m venv .venv
# Windows
. .venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

# 3) Install dependencies
pip install -r requirements.txt
```

## Running the server

You can pass allowed directories either as **positional args** or with **`--allow-dir`** (repeatable). If you pass none, the server falls back to defaults: `~/Downloads`, `~/Desktop`, `~/Documents`, and the current working directory.

```bash
# Example: two directories (mixed platforms shown for clarity)
python main.py ~/Downloads C:\\Temp

# Same via explicit flags (repeatable)
python main.py --allow-dir ~/Downloads --allow-dir C:\\Temp

# Optional tuning
python main.py ~/Downloads --max-file-size 52428800 --log-level DEBUG
```

> Tip (Windows): If you run into import issues while developing, ensure your repo root is on `PYTHONPATH`, e.g. `set PYTHONPATH=C:\\mcp-servers\\pdf-memo-mcp`.

## Claude Desktop integration

Create or update your `claude_desktop_config.json` to register this MCP server. Below is a minimal example.

```jsonc
{
  "mcpServers": {
    "pdf-memo": {
      "command": "C:/Users/yong/AppData/Local/Programs/Python/Python311/python.exe",
      "args": [
        "C:/mcp-servers/pdf-memo-mcp/main.py",
        "~/Downloads",
        "C:/Temp"
      ],
      "env": {
        "PYTHONPATH": "C:/mcp-servers/pdf-memo-mcp"
      }
    }
  }
}
```

**macOS/Linux variant**:

```jsonc
{
  "mcpServers": {
    "pdf-memo": {
      "command": "/usr/bin/python3",
      "args": [
        "/Users/you/mcp-servers/pdf-memo-mcp/main.py",
        "~/Downloads",
        "/Users/you/PDFs"
      ],
      "env": {
        "PYTHONPATH": "/Users/you/mcp-servers/pdf-memo-mcp"
      }
    }
  }
}
```

> Notes
>
> * The server communicates over **STDIO**; Claude Desktop will handle transport automatically.
> * You can add/remove directories later by editing `args` and restarting Claude Desktop.

## Available tools (names & typical usage)

* `extract_annotations(file_path, page_range=None, include_types="Highlight,Text", drop_empty=True)`
  Return raw annotations as JSON. Use `include_types` to include `Link, Popup` if you really need them.

* `extract_highlights_with_context(file_path, page_range=None, drop_empty=True)`
  Return a JSON array of highlight contexts: `{page, author, highlighted_text, note, position}`.

* `read_pdf_text(file_path, page_range=None)`
  Return JSON with `extracted_pages` (page text & char counts) and basic `metadata`.

* `list_pdf_files(directory="all")`
  Human‑readable list of PDFs under allowed directories. `directory` filters by basename substring.

* `show_accessible_directories()`
  JSON with `accessible_directories`, `directory_count`, `max_file_size_mb`, `allowed_extensions`.

### Page range examples

* `"first"` → first page
* `"last"` → last page
* `"3"` → page 3
* `"10-20"` → pages 10 through 20 (inclusive)
* omit the argument → all pages

## Quick start in Claude

Ask natural-language prompts like:

* *“List the PDFs you can see under C:\Temp.”* → `list_pdf_files`
* *“What annotations are on page 162 of ‘Foo.pdf’?”* → `extract_annotations` with `page_range: "162"`
* *“Show me the highlighted text for page 162.”* → `extract_highlights_with_context` with `page_range: "162"`
* *“Read the first page text and metadata.”* → `read_pdf_text` with `page_range: "first"`

## Troubleshooting

* **`ModuleNotFoundError: No module named 'pdf_memo'`**
  Ensure your repo root is on `PYTHONPATH` (see examples above) or run `main.py` from the repo root. This repo also injects `sys.path` in `main.py` for convenience.

* **No highlights found**
  `extract_highlights_with_context` only returns **Highlight** annotations. If your file only has links/popups, use `extract_annotations` and adjust `include_types`.

* **Jumbled text in highlights**
  The mapper prefers `QuadPoints` when present and falls back to `Rect`. It first tries `within_bbox().extract_text()` and then a (y,x) word grouping heuristic. Some PDFs with complex layouts may still need tuning.

## License

MIT License

Copyright (c) 2025 Yong Choi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
