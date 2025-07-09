#!/usr/bin/env python3
"""
PDF Annotator MCP Server
PDF 파일에서 주석(annotations)과 메모를 추출하는 기능을 제공합니다.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import PyPDF2
import pdfplumber
from mcp.server.fastmcp import FastMCP


# --- 기본 설정 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

mcp = FastMCP("PDF Annotator")

# --- 보안 및 경로 설정 ---
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = ['.pdf']
# 파일을 검색할 기본 디렉토리 목록 (우선순위 순)
SEARCH_DIRECTORIES = [
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.getcwd(),
]

def validate_and_resolve_path(file_path: str) -> Optional[Path]:
    """
    사용자가 제공한 파일 경로를 검증하고 절대 경로 Path 객체로 변환합니다.
    보안(경로 순회, 심볼릭 링크, 파일 크기/확장자) 검사를 수행합니다.
    """
    try:
        # 1. 절대 경로로 변환 및 정규화
        if file_path.startswith('~'):
            abs_path = os.path.expanduser(file_path)
        else:
            abs_path = os.path.abspath(file_path)
        
        real_path = os.path.realpath(abs_path)

        # 2. 경로 순회 및 심볼릭 링크 공격 방지
        # realpath가 원래의 abspath가 허용된 디렉토리 내에서 시작하는지 확인
        is_safe = False
        for allowed_dir in SEARCH_DIRECTORIES:
            if os.path.realpath(allowed_dir) in real_path:
                is_safe = True
                break
        
        if not is_safe or '..' in Path(file_path).parts:
            logger.warning(f"보안 위험 감지 (경로 순회 또는 허용되지 않은 접근): {file_path}")
            return None

        # 3. 파일 존재 여부 및 확장자 검증
        resolved_path = Path(real_path)
        if not resolved_path.is_file():
            return None # 파일이 아니면 None 반환 (find_file에서 처리)
            
        if resolved_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            logger.warning(f"허용되지 않은 파일 확장자: {file_path}")
            return None

        # 4. 파일 크기 제한 검증
        if resolved_path.stat().st_size > MAX_FILE_SIZE:
            logger.warning(f"파일 크기 초과: {file_path}")
            return None

        return resolved_path

    except Exception as e:
        logger.error(f"파일 경로 검증 중 오류 발생: {file_path}, 오류: {e}")
        return None

def find_file(file_name: str) -> Optional[Path]:
    """
    단순화된 파일 찾기 함수. 절대 경로를 우선 처리하고, 아니면 지정된 디렉토리에서 검색합니다.
    """
    # 1. 절대/사용자 경로인지 확인
    if file_name.startswith(('/', '~')):
        path = validate_and_resolve_path(file_name)
        if path and path.exists():
            return path
            
    # 2. 지정된 검색 디렉토리에서 순차적으로 검색
    for directory in SEARCH_DIRECTORIES:
        potential_path = Path(directory) / file_name
        path = validate_and_resolve_path(str(potential_path))
        if path and path.exists():
            logger.info(f"파일을 {path} 에서 찾았습니다.")
            return path
    
    logger.warning(f"파일을 찾을 수 없습니다: {file_name}")
    return None

def get_text_within_bbox(bbox: List[float], words: List[Dict[str, Any]]) -> str:
    """
    주어진 경계 상자(bbox) 내에 완전히 또는 부분적으로 포함된 단어들을 찾아 텍스트로 반환합니다.
    """
    x0, top, x1, bottom = bbox
    # 하이라이트 영역이 여러 줄에 걸쳐 있을 수 있으므로, y좌표를 너그럽게 비교합니다.
    # 단어의 중심점이 하이라이트의 수직 범위 안에 있는지 확인합니다.
    overlapping_words = [
        word for word in words
        if not (word['x1'] < x0 or word['x0'] > x1) and \
           ((word['top'] + word['bottom']) / 2) >= top and \
           ((word['top'] + word['bottom']) / 2) <= bottom
    ]
    
    # x 좌표 순으로 단어 정렬
    overlapping_words.sort(key=lambda w: w['x0'])
    
    return " ".join(w['text'] for w in overlapping_words)


# --- PDF 처리 클래스 ---
class PDFAnnotationExtractor:
    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path

    def extract_annotations(self) -> List[Dict[str, Any]]:
        """PyPDF2를 사용하여 주석을 추출합니다."""
        annotations = []
        try:
            with open(self.pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(reader.pages, 1):
                    if "/Annots" in page:
                        for annot in page["/Annots"]:
                            obj = annot.get_object()
                            content = obj.get("/Contents", "")
                            subtype = obj.get("/Subtype", "Unknown")
                            author = obj.get("/T", "")
                            rect = obj.get("/Rect", [])
                            
                            annotations.append({
                                "page": page_num,
                                "type": str(subtype),
                                "content": str(content),
                                "author": str(author),
                                "position": [float(p) for p in rect],
                            })
        except Exception as e:
            logger.error(f"{self.pdf_path} 파일 주석 추출 중 오류: {e}")
        return annotations

    def extract_full_content(self) -> Dict[str, Any]:
        """pdfplumber를 사용하여 전체 텍스트와 메타데이터를 추출합니다."""
        content = {"metadata": {}, "pages": []}
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                content["metadata"] = pdf.metadata
                for i, page in enumerate(pdf.pages, 1):
                    content["pages"].append({
                        "page_number": i,
                        "text": page.extract_text() or "",
                    })
        except Exception as e:
            logger.error(f"{self.pdf_path} 파일 내용 추출 중 오류: {e}")
        return content

# --- MCP 도구 정의 ---
@mcp.tool()
async def extract_pdf_annotations(file_path: str) -> str:
    """PDF 파일에서 주석(메모)을 추출하여 JSON 형식으로 반환합니다."""
    path = find_file(file_path)
    if not path:
        return f"오류: '{file_path}' 파일을 찾을 수 없습니다. 절대 경로를 입력하거나 다음 위치에 파일을 두세요: Downloads, Desktop, Documents."

    try:
        extractor = PDFAnnotationExtractor(path)
        annotations = extractor.extract_annotations()
        if not annotations:
            return f"'{path.name}' 파일에 주석이 없습니다."
        
        result = {
            "file_name": path.name,
            "path": str(path),
            "total_annotations": len(annotations),
            "annotations": annotations,
        }
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"주석 추출 도중 오류: {e}")
        return f"오류: {e}"

@mcp.tool()
async def extract_annotations_summary(file_path: str) -> str:
    """PDF 파일의 주석을 사람이 읽기 좋은 형식으로 요약합니다."""
    path = find_file(file_path)
    if not path:
        return f"오류: '{file_path}' 파일을 찾을 수 없습니다."

    try:
        extractor = PDFAnnotationExtractor(path)
        annotations = extractor.extract_annotations()
        if not annotations:
            return f"'{path.name}' 파일에 주석이 없습니다."

        summary = [f"'{path.name}' 파일 주석 요약 (총 {len(annotations)}개)", "="*40]
        for ann in annotations:
            summary.append(f"📄 페이지 {ann['page']} ({ann['type']})")
            if ann.get('author'):
                summary.append(f"  - 작성자: {ann['author']}")
            if ann.get('content'):
                summary.append(f"  - 내용: {ann['content'][:100]}...") # 내용이 길 경우 일부만 표시
            summary.append("-" * 20)
        return "\n".join(summary)
    except Exception as e:
        logger.error(f"주석 요약 도중 오류: {e}")
        return f"오류: {e}"

@mcp.tool()
async def list_pdf_files(directory_name: str = "Downloads") -> str:
    """지정된 기본 폴더(Downloads, Desktop, Documents)의 PDF 목록을 보여줍니다."""
    dir_map = {
        "downloads": os.path.expanduser("~/Downloads"),
        "desktop": os.path.expanduser("~/Desktop"),
        "documents": os.path.expanduser("~/Documents"),
    }
    
    target_dir_str = dir_map.get(directory_name.lower())
    if not target_dir_str:
        return f"오류: '{directory_name}'은(는) 허용된 폴더가 아닙니다. 'Downloads', 'Desktop', 'Documents' 중 하나를 선택하세요."

    target_dir = Path(target_dir_str)
    if not target_dir.is_dir():
        return f"오류: '{target_dir}' 디렉토리를 찾을 수 없습니다."

    try:
        pdf_files = [f for f in target_dir.glob("*.pdf") if f.is_file()]
        if not pdf_files:
            return f"'{directory_name}' 폴더에 PDF 파일이 없습니다."
        
        result = [f"'{directory_name}' 폴더의 PDF 파일 목록 ({len(pdf_files)}개):", "="*40]
        for pdf in sorted(pdf_files, key=lambda p: p.stat().st_mtime, reverse=True)[:15]: # 최근 15개만 표시
            result.append(f"- {pdf.name} ({pdf.stat().st_size / 1024**2:.1f} MB)")
        return "\n".join(result)
    except Exception as e:
        logger.error(f"'{directory_name}' 폴더 목록 조회 중 오류: {e}")
        return f"오류: {e}"


@mcp.tool()
async def extract_annotations_with_context(file_path: str) -> str:
    """
    PDF에서 주석과 함께, 해당 주석이 적용된 '원문 텍스트'를 정확히 추출합니다.
    """
    path = find_file(file_path)
    if not path:
        return f"오류: '{file_path}' 파일을 찾을 수 없습니다."

    results = []
    try:
        with pdfplumber.open(path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # 페이지의 모든 단어와 그 좌표를 미리 추출
                words = page.extract_words()
                
                # pdfplumber는 /QuadPoints를 더 정확하게 처리하므로 이를 우선 사용
                # PyPDF2의 /Rect보다 하이라이트 영역을 더 잘 표현합니다.
                page_annots = page.annots
                
                if not page_annots:
                    continue

                for annot in page_annots:
                    # 주석의 경계 상자(bounding box)를 가져옵니다.
                    bbox = [
                        float(annot['x0']),
                        float(annot['top']),
                        float(annot['x1']),
                        float(annot['bottom'])
                    ]
                    
                    # 경계 상자 내의 텍스트를 찾습니다.
                    highlighted_text = get_text_within_bbox(bbox, words)
                    
                    # 주석 내용('/Contents')과 작성자('/T') 정보 추출
                    content = annot.get('data', {}).get('contents', '')
                    author = annot.get('data', {}).get('title', '') # pdfplumber에서는 /T를 title로 파싱
                    
                    # 결과가 유의미한 경우에만 추가 (예: 빈 하이라이트 제외)
                    if highlighted_text or content:
                        results.append({
                            "page": page_num,
                            "author": author,
                            "highlighted_text": highlighted_text,
                            "note": content,
                            "position": bbox
                        })
    except Exception as e:
        logger.error(f"주석 및 컨텍스트 추출 중 오류: {e}")
        return f"오류: {e}"

    if not results:
        return f"'{path.name}' 파일에서 주석을 찾을 수 없거나, 텍스트와 연결된 주석이 없습니다."

    # 사람이 읽기 좋은 형식으로 최종 결과 포맷팅
    if not results:
        return json.dumps({"message": f"'{path.name}' 파일에서 주석을 찾을 수 없거나, 텍스트와 연결된 주석이 없습니다."})

    # 추출된 데이터를 JSON 문자열로 변환하여 반환
    return json.dumps(results, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    logger.info("PDF Annotator MCP 서버를 시작합니다...")
    mcp.run(transport='stdio')
