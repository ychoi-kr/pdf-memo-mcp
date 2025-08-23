#!/usr/bin/env python3
"""
PDF Annotator MCP Server (modular)
- Keeps the original separated tool behavior
- Adds: configurable directories, show_accessible_directories, flexible page_range, metadata
"""
import logging
import os
import sys

# Ensure package is importable when running from the repo root or via an MCP launcher
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from pdf_annotator.core.paths import parse_arguments, setup_search_directories, SEARCH_DIRECTORIES
from pdf_annotator.tools.mcp_tools import mcp

if __name__ == "__main__":
    args = parse_arguments()
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    setup_search_directories(args)

    logging.info("Starting PDF Annotator MCP server...")
    logging.info("Accessible directories: %s", " ; ".join(SEARCH_DIRECTORIES))

    mcp.run(transport="stdio")
