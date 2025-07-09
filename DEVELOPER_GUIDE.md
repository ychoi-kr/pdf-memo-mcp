# PDF Annotator MCP Server - Developer Guide

## Overview

This document serves as a comprehensive guide for developers working on the PDF Annotator MCP server. It covers architecture decisions, development guidelines, maintenance notes, and future roadmap.

## Core Architecture

### Hybrid Approach: Resources + Tools

The server provides **multiple complementary access patterns** to accommodate different client capabilities and use cases:

1. **MCP Resources**: Expose PDF files for direct client selection
2. **Search Tools**: Enable natural language file discovery  
3. **URI Tools**: Allow precise file access via resource URIs

This flexibility ensures the server works well with both sophisticated MCP clients and AI agents that need intuitive interfaces.

### Data Processing Pipeline

```
File Discovery → Security Validation → Annotation Extraction → JSON Response
```

- **PyPDF2**: Extract basic annotation metadata (position, type, author, note)
- **pdfplumber**: Extract highlighted text within annotation boundaries
- **Unified Output**: Combine both sources into a consistent data structure

## Development Guidelines

### Security Model

```python
# File access is restricted to these directories only
SEARCH_DIRECTORIES = [
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Desktop"), 
    os.path.expanduser("~/Documents"),
    os.getcwd(),
]
```

**Key validations in `validate_and_resolve_path()`:**
- Path traversal prevention (`..` detection)
- Directory boundary enforcement
- File extension validation (`.pdf` only)
- Size limits (100MB max)

### Tool Design Patterns

#### 1. Natural Language Tools
```python
# Good: Accept flexible input
"find_and_extract_annotations": "CS interview notes"

# Avoid: Require exact paths  
"extract_annotations": "/Users/name/Downloads/exact_file.pdf"
```

#### 2. Structured Data Response
```python
# Always return JSON, never formatted text
return [TextContent(
    type="text",
    text=json.dumps(result, indent=2, ensure_ascii=False)
)]
```

#### 3. Error Handling
```python
# Provide actionable alternatives
if not pdf_path:
    return "Could not find file. Use list_pdf_files tool to see available files."

# Avoid: Dead-end errors
return "File not found."
```

### File Encoding Considerations

Handle Korean/Unicode filenames properly:
```python
# URI decoding for resource paths
file_path = unquote(resource_uri[7:])  # Remove 'file://' prefix

# JSON output with Unicode preservation  
json.dumps(result, ensure_ascii=False)
```

## Tool Relationships

### Complementary, Not Redundant

Each tool serves a specific access pattern:

- **`find_and_extract_annotations`**: AI-friendly natural language search
- **`list_pdf_files`**: Directory browsing and file discovery
- **`extract_annotations_from_uri`**: Direct resource URI processing

### Consistent Underlying Logic

All tools use the same core functions:
- `validate_and_resolve_path()` for security
- `get_unified_annotations()` for data extraction
- JSON formatting for responses

## Maintenance Notes

### When Adding New Features

1. **Security First**: All file access must go through `validate_and_resolve_path()`
2. **JSON Responses**: Never return formatted text strings
3. **Error Context**: Provide helpful alternatives, not just error messages
4. **Unicode Support**: Test with Korean filenames

### When Modifying Annotation Extraction

- Keep the PyPDF2 + pdfplumber combination for comprehensive results
- Maintain the unified data structure format
- Test with various PDF annotation types (highlights, notes, comments)

### Common Pitfalls to Avoid

- **Path Security**: Don't bypass validation for "convenience"
- **String Responses**: Don't format data for human reading in tool responses
- **Error Silence**: Don't fail silently; provide clear feedback
- **Encoding Issues**: Don't assume ASCII-only filenames

## Architecture Decisions

### Why Hybrid Resources + Tools?

- **Resources**: Work well with sophisticated MCP clients that can present file lists
- **Tools**: Essential for AI agents that need natural language interaction
- **Together**: Provide maximum compatibility and flexibility

### Why JSON-Only Responses?

- AI agents can easily parse and reformat structured data
- Prevents data loss from string formatting
- Enables flexible presentation based on user context
- Maintains consistency across all tools

### Why Multiple Libraries for Annotation Extraction?

- **PyPDF2**: Reliable for basic annotation metadata
- **pdfplumber**: Better at extracting highlighted text content
- **Combined**: Provides the most complete annotation data possible

## Future Roadmap

### Phase 1: Enhanced Reading Capabilities (Current)
- ✅ Basic annotation extraction (highlights, notes, comments)
- ✅ Multiple access patterns (Resources + Tools)
- ✅ Security validation and Unicode support
- 🔄 **Next**: Improved annotation type support (shapes, stamps, etc.)

### Phase 2: AI-Assisted Review Features
- 📋 **Text Analysis Tools**: Extract and summarize document content
- 🔍 **Content Search**: Find specific topics or keywords within PDFs
- 📊 **Document Insights**: Generate summaries of annotation patterns
- 🏷️ **Smart Categorization**: Classify annotations by type and importance

### Phase 3: Annotation Writing Capabilities
- ✍️ **Add Annotations**: Create highlights, notes, and comments programmatically
- 🎯 **AI-Powered Markup**: Let AI agents review and annotate documents
- 📝 **Template Annotations**: Pre-defined annotation patterns for common review tasks
- 🔄 **Batch Processing**: Annotate multiple documents with consistent criteria

### Phase 4: Advanced Integration
- 🤝 **Multi-format Support**: Extend beyond PDF to other document types
- 🌐 **Cloud Integration**: Work with cloud-stored documents
- 👥 **Collaborative Features**: Support multi-user annotation workflows
- 🔗 **External Tools**: Integration with note-taking and document management systems

### Implementation Considerations for Future Phases

#### Annotation Writing Architecture
```python
# Future tool structure for writing annotations
@mcp.call_tool()
async def add_annotation_to_pdf(
    file_path: str,
    page_number: int,
    annotation_type: str,  # "highlight", "note", "comment"
    content: str,
    position: Optional[Dict] = None  # Auto-detect if not provided
) -> Sequence[TextContent]:
    # Implementation using PyPDF2 writer capabilities
    pass
```

#### AI Review Workflow Example
```python
# AI agent workflow for document review
1. extract_annotations_with_context(file_path)
2. analyze_document_content(file_path) 
3. add_annotation_to_pdf(file_path, suggestions...)
4. generate_review_summary(file_path)
```

#### Security for Write Operations
- **Read-only by default**: Writing requires explicit permission
- **Backup creation**: Always create backup before modifying files
- **Transaction safety**: Atomic operations to prevent file corruption
- **Audit logging**: Track all modification operations

#### Technical Challenges to Address
- **PDF Compatibility**: Not all PDFs support annotation writing
- **Library Limitations**: PyPDF2 write capabilities vs. alternatives
- **File Locking**: Handle concurrent access to files
- **Version Control**: Track document modification history
