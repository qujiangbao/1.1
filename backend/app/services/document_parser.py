"""DocumentParser — PDF/DOCX/HTML 文本提取

支持: .pdf、.docx、.pptx、.xlsx、.csv、.html、.txt、.md
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from zipfile import BadZipFile, ZipFile, is_zipfile

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

    SUPPORTED = {
        ".pdf", ".docx", ".pptx", ".xlsx", ".csv",
        ".html", ".htm", ".txt", ".md",
    }
    MAX_FILE_BYTES = 25 * 1024 * 1024
    MAX_EXTRACTED_CHARS = 5_000_000
    MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
    MAX_ARCHIVE_MEMBERS = 2_000
    MAX_PDF_PAGES = 1_000
    MAX_SPREADSHEET_ROWS = 20_000
    MAX_SPREADSHEET_COLUMNS = 200
    MAX_WORKSHEETS = 30

    async def parse(self, file_path: str) -> ParsedDocument:
        """Parse a document off the event loop because readers are blocking."""
        return await asyncio.to_thread(self._parse_sync, file_path)

    def _parse_sync(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        if not path.exists():
            return ParsedDocument(raw_text="", filename=path.name, error=f"File not found: {file_path}")

        ext = path.suffix.lower()
        if ext not in self.SUPPORTED:
            return ParsedDocument(raw_text="", filename=path.name, error=f"Unsupported format: {ext}")

        file_size = path.stat().st_size
        if file_size > self.MAX_FILE_BYTES:
            return ParsedDocument(
                raw_text="",
                filename=path.name,
                file_size=file_size,
                error="Document exceeds the 25 MB limit",
            )
        file_hash = self._hash_file(path)

        try:
            if ext == ".pdf":
                if not self._has_prefix(path, b"%PDF-"):
                    raise ValueError("File content is not a valid PDF")
                text, pages = self._parse_pdf(str(path))
            elif ext == ".docx":
                self._validate_office_archive(path)
                text, pages = self._parse_docx(str(path))
            elif ext == ".pptx":
                self._validate_office_archive(path)
                text, pages = self._parse_pptx(str(path))
            elif ext == ".xlsx":
                self._validate_office_archive(path)
                text, pages = self._parse_xlsx(str(path))
            elif ext == ".csv":
                text, pages = self._parse_csv(str(path))
            elif ext in (".html", ".htm"):
                text, pages = self._parse_html(str(path))
            else:
                text = path.read_text(encoding="utf-8")
                pages = 1

            if len(text) > self.MAX_EXTRACTED_CHARS:
                raise ValueError("Extracted document text exceeds the safe limit")

            return ParsedDocument(
                raw_text=text.strip(),
                page_count=pages,
                file_format=ext,
                file_hash=file_hash,
                file_size=file_size,
                filename=path.name,
            )
        except Exception as exc:
            logger.exception("Document parse failed for filename=%s", path.name)
            detail = (
                str(exc)
                if isinstance(exc, (ValueError, UnicodeError, BadZipFile))
                else "Document parsing failed"
            )
            return ParsedDocument(raw_text="", filename=path.name, error=detail)

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()[:16]

    @staticmethod
    def _has_prefix(path: Path, prefix: bytes) -> bool:
        with path.open("rb") as stream:
            return stream.read(len(prefix)) == prefix

    def _validate_office_archive(self, path: Path) -> None:
        """Reject disguised Office files and archives with unsafe expansion."""
        if not is_zipfile(path):
            raise ValueError("File content is not a valid Office document")
        with ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > self.MAX_ARCHIVE_MEMBERS:
                raise ValueError("Office document contains too many archive members")
            expanded_size = sum(member.file_size for member in members)
            if expanded_size > self.MAX_ARCHIVE_BYTES:
                raise ValueError("Office document expands beyond the safe limit")

    def _parse_pdf(self, path: str) -> tuple[str, int]:
        try:
            from pypdf import PdfReader
            doc = PdfReader(path)
            if len(doc.pages) > self.MAX_PDF_PAGES:
                raise ValueError("PDF contains too many pages")
            parts: list[str] = []
            total = 0
            for page in doc.pages:
                page_text = page.extract_text() or ""
                total += len(page_text)
                if total > self.MAX_EXTRACTED_CHARS:
                    raise ValueError("Extracted document text exceeds the safe limit")
                parts.append(page_text)
            text = "\n\n".join(parts)
            return text, len(doc.pages)
        except ImportError:
            raise ImportError("需要安装 pypdf 来解析 PDF")

    def _parse_docx(self, path: str) -> tuple[str, int]:
        try:
            from docx import Document
            doc = Document(path)
            parts = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
                if rows:
                    parts.append(self._rows_to_markdown(rows))
            text = "\n\n".join(parts)
            return text, 1
        except ImportError:
            raise ImportError("需要安装 python-docx 来解析 DOCX")

    def _parse_pptx(self, path: str) -> tuple[str, int]:
        try:
            from pptx import Presentation
            presentation = Presentation(path)
            slides: list[str] = []
            for slide in presentation.slides:
                parts: list[str] = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        parts.append(shape.text)
                    if getattr(shape, "has_table", False):
                        for row in shape.table.rows:
                            parts.append(" | ".join(cell.text for cell in row.cells))
                slides.append("\n".join(parts))
            return "\n\n".join(slides), len(presentation.slides)
        except ImportError:
            raise ImportError("需要安装 python-pptx 来解析 PPTX")

    @staticmethod
    def _markdown_cell(value: object) -> str:
        return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ").strip()

    def _rows_to_markdown(self, rows: list[list[object]]) -> str:
        if not rows:
            return ""
        width = max(len(row) for row in rows)
        width = min(width, self.MAX_SPREADSHEET_COLUMNS)
        normalized = [
            [self._markdown_cell(row[index] if index < len(row) else "") for index in range(width)]
            for row in rows
        ]
        return "\n".join([
            "| " + " | ".join(normalized[0]) + " |",
            "| " + " | ".join("---" for _ in range(width)) + " |",
            *("| " + " | ".join(row) + " |" for row in normalized[1:]),
        ])

    def _parse_csv(self, path: str) -> tuple[str, int]:
        raw = Path(path).read_bytes()
        text = None
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ValueError("CSV 必须使用 UTF-8 或 GB18030 编码")
        sample = text[:8192]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        except csv.Error:
            dialect = csv.excel
        rows: list[list[object]] = []
        for index, row in enumerate(csv.reader(text.splitlines(), dialect)):
            if index >= self.MAX_SPREADSHEET_ROWS:
                raise ValueError("CSV 数据行数超过 20000 行限制")
            if len(row) > self.MAX_SPREADSHEET_COLUMNS:
                raise ValueError("CSV 列数超过 200 列限制")
            if any(str(cell).strip() for cell in row):
                rows.append(row)
        if len(rows) < 2:
            raise ValueError("CSV 至少需要表头和一行数据")
        return self._rows_to_markdown(rows), max(1, len(rows) - 1)

    def _parse_xlsx(self, path: str) -> tuple[str, int]:
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise ImportError("需要安装 openpyxl 来解析 XLSX") from exc
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            if len(workbook.worksheets) > self.MAX_WORKSHEETS:
                raise ValueError("XLSX 工作表数量超过 30 个限制")
            sections: list[str] = []
            total_rows = 0
            for sheet in workbook.worksheets:
                rows: list[list[object]] = []
                for row in sheet.iter_rows(values_only=True):
                    values = list(row)
                    if not any(value not in (None, "") for value in values):
                        continue
                    total_rows += 1
                    if total_rows > self.MAX_SPREADSHEET_ROWS:
                        raise ValueError("XLSX 数据行数超过 20000 行限制")
                    if len(values) > self.MAX_SPREADSHEET_COLUMNS:
                        raise ValueError("XLSX 列数超过 200 列限制")
                    rows.append(values)
                if rows:
                    sections.append(f"# 工作表：{sheet.title}\n\n{self._rows_to_markdown(rows)}")
            if not sections:
                raise ValueError("XLSX 中没有可读取的数据")
            return "\n\n".join(sections), len(workbook.worksheets)
        finally:
            workbook.close()

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
