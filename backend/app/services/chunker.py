"""TextChunker — 章节感知的文本分块

策略: 优先按章节标题分割，每个章节内滑动窗口分块。
chunk_size: 512 tokens (~1200 中文字符), overlap: 50 tokens
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import List
from app.services.metadata_extractor import PolicyMetadata


@dataclass
class ChunkData:
    chunk_id: str
    policy_id: str = ""
    chunk_index: int = 0
    content: str = ""
    content_hash: str = ""
    token_count: int = 0
    metadata: dict = field(default_factory=dict)


class TextChunker:
    """章节感知文本分块器"""

    # 中文章节标题正则
    SECTION_PATTERNS = [
        r"^第[一二三四五六七八九十百千\d]+章",         # 第X章
        r"^[一二三四五六七八九十]+、",                 # 一、二、
        r"^（[一二三四五六七八九十]+）",               # （一）
        r"^\d+[\.、]",                                 # 1. 2.
    ]

    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(
        self, text: str, metadata: PolicyMetadata, policy_id: str = ""
    ) -> List[ChunkData]:
        """主入口: 文本 → 分块列表"""
        sections = self._split_by_sections(text)

        chunks: List[ChunkData] = []
        idx = 0

        for section_title, section_text in sections:
            section_chunks = self._sliding_window(section_text)
            for chunk_text in section_chunks:
                chunk_meta = metadata.to_dict()
                chunk_meta["section"] = section_title
                chunk_meta["policy_id"] = policy_id

                chunks.append(ChunkData(
                    chunk_id=f"{policy_id}-c{idx:03d}",
                    policy_id=policy_id,
                    chunk_index=idx,
                    content=chunk_text,
                    content_hash=hashlib.sha256(chunk_text.encode()).hexdigest()[:16],
                    token_count=self._estimate_tokens(chunk_text),
                    metadata=chunk_meta,
                ))
                idx += 1

        return chunks

    def _split_by_sections(self, text: str) -> List[tuple[str, str]]:
        """按章节标题分割"""
        pattern = "|".join(f"({p})" for p in self.SECTION_PATTERNS)
        compiled = re.compile(pattern, re.MULTILINE)

        parts = compiled.split(text)
        sections = []

        current_title = ""
        current_text = ""

        for part in parts:
            if part is None:
                continue
            if compiled.match(part):
                if current_text.strip():
                    sections.append((current_title, current_text.strip()))
                current_title = part.strip()
                current_text = ""
            else:
                current_text += part

        if current_text.strip() or current_title:
            sections.append((current_title, current_text.strip()))

        # 如果没分出章节，整篇为一个部分
        if not sections:
            sections = [("", text.strip())]

        return sections

    def _sliding_window(self, text: str) -> List[str]:
        """滑动窗口分块"""
        if not text.strip():
            return []

        # 简单策略: 按段落分割后拼接到 chunk_size
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        chunks = []
        current = ""
        current_len = 0

        for para in paragraphs:
            para_len = len(para)
            if current_len + para_len > self.chunk_size * 2 and current:
                chunks.append(current.strip())
                # overlap: 保留最后一段
                overlap_text = current[-self.overlap:] if len(current) > self.overlap else ""
                current = overlap_text + para
                current_len = len(current)
            else:
                if current:
                    current += "\n" + para
                else:
                    current = para
                current_len += para_len

        if current.strip():
            chunks.append(current.strip())

        return chunks

    def _estimate_tokens(self, text: str) -> int:
        """粗略估算 token 数 (中文 ≈ 1.5 char/token)"""
        return max(1, len(text) // 2)
