"""DocumentParser — PDF/DOCX/HTML 文本提取

支持: .pdf (PyMuPDF), .docx (python-docx), .html (BeautifulSoup), .txt
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ParsedDocument:
    """解析后的文档"""
    raw_text: str
    page_count: int = 1
    file_format: str = ""
    file_hash: str = ""
    file_size: int = 0
    filename: str = ""
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return bool(self.raw_text) and self.error is None


class DocumentParser:
    """文档解析器"""

    SUPPORTED = {".pdf", ".docx", ".html", ".htm", ".txt", ".md"}

    async def parse(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        if not path.exists():
            return ParsedDocument(raw_text="", filename=path.name, error=f"File not found: {file_path}")

        ext = path.suffix.lower()
        if ext not in self.SUPPORTED:
            return ParsedDocument(raw_text="", filename=path.name, error=f"Unsupported format: {ext}")

        file_size = path.stat().st_size
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()[:16]

        try:
            if ext == ".pdf":
                text, pages = self._parse_pdf(str(path))
            elif ext == ".docx":
                text, pages = self._parse_docx(str(path))
            elif ext in (".html", ".htm"):
                text, pages = self._parse_html(str(path))
            else:
                text = path.read_text(encoding="utf-8")
                pages = 1

            return ParsedDocument(
                raw_text=text.strip(),
                page_count=pages,
                file_format=ext,
                file_hash=file_hash,
                file_size=file_size,
                filename=path.name,
            )
        except Exception as e:
            logger.error(f"Parse failed for {file_path}: {e}")
            return ParsedDocument(raw_text="", filename=path.name, error=str(e))

    def _parse_pdf(self, path: str) -> tuple[str, int]:
        try:
            import fitz
            doc = fitz.open(path)
            text = "\n\n".join(page.get_text() for page in doc)
            return text, len(doc)
        except ImportError:
            logger.warning("PyMuPDF not installed, trying pdfplumber")
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    text = "\n\n".join(page.extract_text() or "" for page in pdf.pages)
                    return text, len(pdf.pages)
            except ImportError:
                raise ImportError("需要安装 pymupdf 或 pdfplumber 来解析 PDF")

    def _parse_docx(self, path: str) -> tuple[str, int]:
        try:
            from docx import Document
            doc = Document(path)
            text = "\n".join(p.text for p in doc.paragraphs)
            return text, 1
        except ImportError:
            raise ImportError("需要安装 python-docx 来解析 DOCX")

    def _parse_html(self, path: str) -> tuple[str, int]:
        try:
            from bs4 import BeautifulSoup
            with open(path, encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            return soup.get_text("\n", strip=True), 1
        except ImportError:
            with open(path, encoding="utf-8") as f:
                import re
                text = re.sub(r"<[^>]+>", "", f.read())
            return text, 1
