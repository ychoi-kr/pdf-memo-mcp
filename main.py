#!/usr/bin/env python3
"""
PDF Annotator MCP Server
A hybrid approach that provides both Resources and user-friendly Tools
for PDF annotation extraction. This combines the best of both worlds.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import unquote

import PyPDF2
import pdfplumber
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent

# --- Basic Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PDFAnnotator")
mcp = Server("PDF Annotator")

# --- Security and Path Configuration ---
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = ['.pdf']
SEARCH_DIRECTORIES = [
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.getcwd(),
]

def validate_and_resolve_path(file_path: str) -> Optional[Path]:
    """
    Validates and resolves a file path to an absolute Path object.
    Performs security checks (path traversal, symlinks, file size/extensions).
    """
    try:
        # Convert to absolute path
        if file_path.startswith('~'):
            abs_path = os.path.expanduser(file_path)
        else:
            abs_path = os.path.abspath(file_path)
        
        real_path = os.path.realpath(abs_path)

        # Security check: prevent path traversal
        is_safe = False
        for allowed_dir in SEARCH_DIRECTORIES:
            if os.path.realpath(allowed_dir) in real_path:
                is_safe = True
                break
        
        if not is_safe or '..' in Path(file_path).parts:
            logger.warning(f"Security risk detected: {file_path}")
            return None

        resolved_path = Path(real_path)
        
        # Check file existence and extension
        if not resolved_path.is_file():
            return None
            
        if resolved_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            logger.warning(f"Disallowed file extension: {file_path}")
            return None

        # Check file size
        if resolved_path.stat().st_size > MAX_FILE_SIZE:
            logger.warning(f"File too large: {file_path}")
            return None

        return resolved_path

    except Exception as e:
        logger.error(f"Error validating path {file_path}: {e}")
        return None

def find_file(file_name: str) -> Optional[Path]:
    """
    Finds a file by name, checking absolute paths first, then searching directories.
    """
    # Check if it's an absolute path
    if file_name.startswith(('/', '~')):
        path = validate_and_resolve_path(file_name)
        if path and path.exists():
            return path
            
    # Search in designated directories
    for directory in SEARCH_DIRECTORIES:
        potential_path = Path(directory) / file_name
        path = validate_and_resolve_path(str(potential_path))
        if path and path.exists():
            logger.info(f"Found file at {path}")
            return path
    
    logger.warning(f"File not found: {file_name}")
    return None

def get_text_within_bbox(bbox: List[float], words: List[Dict[str, Any]]) -> str:
    """
    Finds words within a bounding box and returns them as text.
    """
    x0, top, x1, bottom = bbox
    overlapping_words = [
        word for word in words
        if not (word['x1'] < x0 or word['x0'] > x1) and \
           ((word['top'] + word['bottom']) / 2) >= top and \
           ((word['top'] + word['bottom']) / 2) <= bottom
    ]
    
    overlapping_words.sort(key=lambda w: w['x0'])
    return " ".join(w['text'] for w in overlapping_words)

def get_unified_annotations(pdf_path: Path) -> List[Dict[str, Any]]:
    """
    Extracts annotations using both PyPDF2 and pdfplumber for comprehensive results.
    """
    base_annotations = []
    
    # First, get basic annotation data with PyPDF2
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page_num, page in enumerate(reader.pages, 1):
                if "/Annots" in page:
                    for annot in page["/Annots"]:
                        obj = annot.get_object()
                        base_annotations.append({
                            "page": page_num,
                            "type": str(obj.get("/Subtype", "Unknown")).strip('/'),
                            "note": str(obj.get("/Contents", "")),
                            "author": str(obj.get("/T", "")),
                            "position": [float(p) for p in obj.get("/Rect", [])],
                        })
    except Exception as e:
        logger.error(f"PyPDF2 extraction failed for {pdf_path}: {e}")
        return []

    if not base_annotations:
        return []

    # Enhance with highlighted text using pdfplumber
    unified_annotations = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for base_annot in base_annotations:
                page_index = base_annot["page"] - 1
                if page_index < len(pdf.pages):
                    page = pdf.pages[page_index]
                    words = page.extract_words()
                    highlighted_text = get_text_within_bbox(base_annot["position"], words)
                    
                    if highlighted_text or base_annot.get("note"):
                        enhanced_annot = base_annot.copy()
                        enhanced_annot["highlighted_text"] = highlighted_text
                        unified_annotations.append(enhanced_annot)
    except Exception as e:
        logger.error(f"pdfplumber enhancement failed for {pdf_path}: {e}")
        return base_annotations

    return unified_annotations

# --- MCP Resource Handlers ---

@mcp.list_resources()
async def list_available_pdfs() -> List[Resource]:
    """
    Exposes all accessible PDF files as MCP Resources.
    This allows clients to see and select files directly.
    """
    resources = {}
    
    for directory in SEARCH_DIRECTORIES:
        try:
            dir_path = Path(directory)
            if not dir_path.exists():
                continue
                
            for pdf_path in dir_path.glob('*.pdf'):
                if pdf_path.is_file() and validate_and_resolve_path(str(pdf_path)):
                    # Create a clean URI
                    file_uri = pdf_path.as_uri()
                    
                    # Avoid duplicates
                    if file_uri not in resources:
                        resources[file_uri] = Resource(
                            uri=file_uri,
                            name=pdf_path.name,
                            description=f"PDF file in {dir_path.name} folder",
                            mimeType="application/pdf"
                        )
        except Exception as e:
            logger.error(f"Error listing resources in {directory}: {e}")
    
    return list(resources.values())

@mcp.read_resource()
async def read_resource(uri: str) -> str:
    """
    Reads a PDF resource and returns its annotation data.
    This is called when a client accesses a resource URI.
    """
    try:
        # Parse the URI to get the file path
        if not uri.startswith('file://'):
            raise ValueError("Only file:// URIs are supported")
        
        # Decode the URI path
        file_path = unquote(uri[7:])  # Remove 'file://' prefix
        pdf_path = Path(file_path)
        
        # Validate the path
        if not validate_and_resolve_path(str(pdf_path)):
            raise ValueError(f"Invalid or inaccessible file: {uri}")
        
        # Extract annotations
        annotations = get_unified_annotations(pdf_path)
        
        if not annotations:
            return json.dumps({
                "file_name": pdf_path.name,
                "message": "No annotations found in this PDF file."
            }, ensure_ascii=False)
        
        return json.dumps({
            "file_name": pdf_path.name,
            "total_annotations": len(annotations),
            "annotations": annotations
        }, indent=2, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"Error reading resource {uri}: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)

# --- MCP Tool Handlers ---

@mcp.list_tools()
async def list_tools() -> List[Tool]:
    """
    Defines the tools available for PDF annotation extraction.
    """
    return [
        Tool(
            name="find_and_extract_annotations",
            description="Find a PDF file by name/keyword and extract its annotations with highlighted text",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_name_or_keyword": {
                        "type": "string",
                        "description": "PDF file name or keyword to search for (e.g., 'interview', 'CS면접원고.pdf')"
                    }
                },
                "required": ["file_name_or_keyword"]
            }
        ),
        Tool(
            name="list_pdf_files",
            description="List all available PDF files in the accessible directories",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory to search in (Downloads, Desktop, Documents, or 'all')",
                        "enum": ["Downloads", "Desktop", "Documents", "all"]
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="extract_annotations_from_uri",
            description="Extract annotations from a specific PDF file URI (from the resource list)",
            inputSchema={
                "type": "object",
                "properties": {
                    "resource_uri": {
                        "type": "string",
                        "description": "The file:// URI of the PDF resource"
                    }
                },
                "required": ["resource_uri"]
            }
        )
    ]

@mcp.call_tool()
async def call_tool(name: str, arguments: dict) -> Sequence[TextContent]:
    """
    Handles tool execution for PDF annotation extraction.
    """
    try:
        if name == "find_and_extract_annotations":
            file_name_or_keyword = arguments.get("file_name_or_keyword", "")
            
            # First, try to find the file directly
            pdf_path = find_file(file_name_or_keyword)
            
            # If not found, search by keyword
            if not pdf_path:
                for directory in SEARCH_DIRECTORIES:
                    try:
                        for potential_file in Path(directory).glob('*.pdf'):
                            if file_name_or_keyword.lower() in potential_file.name.lower():
                                pdf_path = validate_and_resolve_path(str(potential_file))
                                if pdf_path:
                                    break
                        if pdf_path:
                            break
                    except Exception:
                        continue
            
            if not pdf_path:
                return [TextContent(
                    type="text",
                    text=f"Could not find PDF file matching '{file_name_or_keyword}'. Please check the filename or use the list_pdf_files tool to see available files."
                )]
            
            # Extract annotations
            annotations = get_unified_annotations(pdf_path)
            
            if not annotations:
                return [TextContent(
                    type="text",
                    text=f"No annotations found in '{pdf_path.name}'"
                )]
            
            # Format the results in a user-friendly way
            result = {
                "file_name": pdf_path.name,
                "file_path": str(pdf_path),
                "total_annotations": len(annotations),
                "annotations": annotations
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2, ensure_ascii=False)
            )]
        
        elif name == "list_pdf_files":
            directory = arguments.get("directory", "all")
            
            if directory == "all":
                search_dirs = SEARCH_DIRECTORIES
            else:
                dir_map = {
                    "Downloads": os.path.expanduser("~/Downloads"),
                    "Desktop": os.path.expanduser("~/Desktop"),
                    "Documents": os.path.expanduser("~/Documents")
                }
                search_dirs = [dir_map.get(directory, directory)]
            
            all_files = []
            for dir_path in search_dirs:
                try:
                    for pdf_file in Path(dir_path).glob('*.pdf'):
                        if pdf_file.is_file() and validate_and_resolve_path(str(pdf_file)):
                            all_files.append({
                                "name": pdf_file.name,
                                "path": str(pdf_file),
                                "directory": Path(dir_path).name,
                                "size_mb": round(pdf_file.stat().st_size / (1024*1024), 2)
                            })
                except Exception as e:
                    logger.error(f"Error listing files in {dir_path}: {e}")
            
            if not all_files:
                return [TextContent(
                    type="text",
                    text="No PDF files found in the accessible directories."
                )]
            
            # Sort by modification time (most recent first)
            all_files.sort(key=lambda x: Path(x["path"]).stat().st_mtime, reverse=True)
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "total_files": len(all_files),
                    "files": all_files
                }, indent=2, ensure_ascii=False)
            )]
        
        elif name == "extract_annotations_from_uri":
            resource_uri = arguments.get("resource_uri", "")
            
            if not resource_uri.startswith('file://'):
                return [TextContent(
                    type="text",
                    text="Invalid URI format. Must be a file:// URI."
                )]
            
            # Use the same logic as read_resource but return as tool result
            file_path = unquote(resource_uri[7:])
            pdf_path = Path(file_path)
            
            if not validate_and_resolve_path(str(pdf_path)):
                return [TextContent(
                    type="text",
                    text=f"Invalid or inaccessible file: {resource_uri}"
                )]
            
            annotations = get_unified_annotations(pdf_path)
            
            if not annotations:
                return [TextContent(
                    type="text",
                    text=f"No annotations found in '{pdf_path.name}'"
                )]
            
            result = {
                "file_name": pdf_path.name,
                "total_annotations": len(annotations),
                "annotations": annotations
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2, ensure_ascii=False)
            )]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
            
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}")
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]

# --- Main Server Execution ---
async def main():
    """
    Sets up and runs the MCP server with both Resources and Tools.
    """
    logger.info("Starting PDF Annotator MCP Server (Hybrid Version)...")
    
    # Create server initialization options
    options = mcp.create_initialization_options()
    
    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        await mcp.run(read_stream, write_stream, options)

if __name__ == "__main__":
    asyncio.run(main())
