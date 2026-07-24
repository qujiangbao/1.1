"""MetadataExtractor — 从政策文本提取结构化元数据"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class PolicyMetadata:
    """政策元数据"""
    title: str = ""
    department: str = ""
    level: str = ""            # national | provincial | municipal | district
    category: str = ""
    industry_scope: List[str] = field(default_factory=list)
    region_scope: List[str] = field(default_factory=list)
    publish_date: Optional[str] = None
    expire_date: Optional[str] = None
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "department": self.department,
            "level": self.level,
            "category": self.category,
            "industry_scope": self.industry_scope,
            "region_scope": self.region_scope,
            "publish_date": self.publish_date,
            "expire_date": self.expire_date,
            "keywords": self.keywords,
        }


class MetadataExtractor:
    """从文件名和文本前 500 字符提取元数据"""

    LEVEL_PATTERNS = {
        "national":   [r"国务院", r"工信部", r"科技部", r"发改委", r"财政部", r"国家"],
        "provincial": [r"广东省", r"省工信厅", r"省科技厅", r"省发改委", r"省政府"],
        "municipal":  [r"广州市", r"市工信局", r"市科技局", r"市商务局"],
        "district":   [r"黄埔区", r"天河区", r"南沙区", r"区工信局", r"开发区"],
    }

    DEPT_PATTERNS = [
        r"([\u4e00-\u9fff]{2,6}(?:厅|局|部|委|办|会))",
    ]

    INDUSTRY_KEYWORDS = [
        "机器人", "人工智能", "智能制造", "新能源", "生物医药",
        "电子信息", "新材料", "集成电路", "数字经济", "汽车",
    ]

    def extract(self, text: str, filename: str = "") -> PolicyMetadata:
        meta = PolicyMetadata()

        # 标题: 优先文件名（去掉扩展名），次选首行
        if filename:
            name = re.sub(r"\.[^.]+$", "", filename)
            meta.title = name
        else:
            lines = text.strip().split("\n")
            if lines:
                meta.title = lines[0].strip()[:100]

        # 分析文本前 1000 字符
        head = text[:1000]

        # 级别
        for level, patterns in self.LEVEL_PATTERNS.items():
            if any(re.search(p, head) for p in patterns):
                meta.level = level
                break

        # 发文部门
        dept_match = re.search("|".join(self.DEPT_PATTERNS), head)
        if dept_match:
            meta.department = dept_match.group(0)

        # 日期
        date_patterns = [
            r"(\d{4})年(\d{1,2})月(\d{1,2})日",
            r"(\d{4})-(\d{1,2})-(\d{1,2})",
        ]
        dates = []
        for p in date_patterns:
            dates.extend(re.findall(p, head))
        if dates:
            y, m, d = dates[0]
            meta.publish_date = f"{y}-{int(m):02d}-{int(d):02d}"

        # 行业
        for kw in self.INDUSTRY_KEYWORDS:
            if kw in head:
                meta.industry_scope.append(kw)

        # 地区
        region_map = {
            "广东省": ["广东", "广东省"],
            "广州市": ["广州", "广州市"],
            "深圳市": ["深圳", "深圳市"],
            "黄埔区": ["黄埔区", "黄埔"],
            "南沙区": ["南沙区", "南沙"],
        }
        for region, patterns in region_map.items():
            if any(p in head for p in patterns):
                meta.region_scope.append(region)

        # 关键词
        for kw in self.INDUSTRY_KEYWORDS + ["补贴", "税收", "资金", "扶持", "人才"]:
            if kw in head and kw not in meta.keywords:
                meta.keywords.append(kw)

        return meta
