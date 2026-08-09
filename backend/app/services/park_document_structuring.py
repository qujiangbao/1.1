"""Deterministic extraction of enterprise facts from park-owned documents.

The extractor deliberately handles only explicit Markdown headings and table
rows.  It does not ask an LLM to invent missing facts and it keeps every
derived record linked to the uploaded document that supplied the evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Any


COMPANY_PATTERN = re.compile(
    r"([\u4e00-\u9fffA-Za-z0-9（）()·]{2,80}?(?:集团股份有限公司|股份有限公司|有限责任公司|有限公司))"
)
FIELD_ALIASES = {
    "credit_code": ("统一社会信用代码", "社会信用代码"),
    "legal_representative": ("法定代表人", "法人代表"),
    "registered_capital": ("注册资本",),
    "establishment_date": ("成立日期", "成立时间"),
    "registered_address": ("注册地址", "注册地"),
    "enterprise_status": ("经营状态", "登记状态"),
    "enterprise_type": ("公司类型", "企业类型"),
    "business_scope": ("经营范围",),
    "employee_count": ("员工总数", "在职员工总数", "参保人数"),
    "patent_count": ("专利数量", "专利数"),
    "website": ("官方网站", "官网"),
}
RISK_TYPES = {
    "经营异常": "operation",
    "严重违法失信": "credit",
    "被执行": "judicial",
    "诉讼": "judicial",
    "司法": "judicial",
    "处罚": "administrative",
    "监管": "administrative",
    "环保": "administrative",
    "消防": "administrative",
    "安全生产": "administrative",
    "税": "tax",
}
INDUSTRY_RULES = (
    ("robotics", ("机器人", "机械臂", "伺服", "减速器", "无人机", "具身智能")),
    ("ai", ("人工智能", "大模型", "计算机视觉", "AI技术", "AI应用")),
    ("smart_manufacturing", ("智能制造", "自动化", "智能装备", "系统集成")),
    ("nev", ("新能源汽车", "汽车", "动力电池")),
    ("semiconductor", ("半导体", "芯片", "传感器")),
    ("integrated_circuits", ("集成电路", "IC设计")),
    ("biopharma", ("生物医药", "医疗器械", "制药")),
    ("digital_economy", ("软件开发", "大数据", "数字创意", "信息系统", "数据服务")),
    ("新材料", ("新材料", "化学材料", "合成材料")),
)


def _clean(value: str) -> str:
    return re.sub(r"[*`_]+", "", value or "").strip()


def _table_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [_clean(cell) for cell in line.strip().strip("|").split("|")]
        if not cells or all(re.fullmatch(r":?-{2,}:?", cell or "") for cell in cells):
            continue
        rows.append(cells)
    return rows


def _company_name(value: str) -> str | None:
    match = COMPANY_PATTERN.search(_clean(value))
    return match.group(1).strip("：:，,。 ") if match else None


def _sections(text: str) -> list[tuple[str, str]]:
    headings = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", text))
    sections: list[tuple[str, str]] = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        name = _company_name(heading.group(1))
        body = text[heading.end():end]
        if not name:
            for row in _table_rows(body)[:8]:
                if len(row) >= 2 and row[0] == "企业名称":
                    name = _company_name(row[1])
                    break
        if name:
            sections.append((name, body))
    return sections


def _wide_table_sections(text: str) -> list[tuple[str, str]]:
    """Convert a CSV/XLSX-style enterprise wide table into normal sections."""
    output: list[tuple[str, str]] = []
    blocks = re.split(r"\n\s*\n", text)
    for block in blocks:
        rows = _table_rows(block)
        if len(rows) < 2:
            continue
        headers = [re.sub(r"[\s*]", "", cell) for cell in rows[0]]
        name_index = next(
            (index for index, header in enumerate(headers) if header in {"企业名称", "公司名称"}),
            None,
        )
        if name_index is None:
            continue
        for row in rows[1:]:
            if name_index >= len(row):
                continue
            name = _company_name(row[name_index])
            if not name:
                continue
            vertical_rows = []
            for index, header in enumerate(headers):
                value = row[index] if index < len(row) else ""
                if header and value:
                    vertical_rows.append(f"| {header} | {value} |")
            output.append((name, "\n".join(vertical_rows)))
    return output


def _row_value(rows: list[list[str]], aliases: tuple[str, ...]) -> str | None:
    for row in rows:
        if len(row) < 2:
            continue
        label = re.sub(r"[\s*]", "", row[0])
        if any(alias in label for alias in aliases):
            value = _clean(row[1])
            if value and value not in {"—", "-", "未公开", "待核验"}:
                return value
    return None


def _number(value: str | None, *, capital: bool = False) -> float | None:
    if not value:
        return None
    match = re.search(r"([\d,.]+)", value)
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    if capital and "亿" in value:
        number *= 10000
    return number


def _industry(name: str, body: str) -> tuple[str, list[str]]:
    searchable = f"{name} {body}"
    hits: list[tuple[str, int, list[str]]] = []
    for code, terms in INDUSTRY_RULES:
        matched = [term for term in terms if term.lower() in searchable.lower()]
        if matched:
            hits.append((code, len(matched), matched))
    if not hits:
        return "未分类", []
    hits.sort(key=lambda item: item[1], reverse=True)
    return hits[0][0], hits[0][2][:8]


def _risk_events(
    rows: list[list[str]], *, enterprise_id: str, source_title: str, document_id: str
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in rows:
        if len(row) < 3:
            continue
        label, status, detail = row[0], row[1], row[2]
        event_type = next((kind for term, kind in RISK_TYPES.items() if term in label), None)
        if not event_type:
            continue
        combined = f"{status} {detail}"
        negative = any(term in combined for term in (
            "无记录", "未发现", "无处罚", "近五年无", "不构成重大违法",
        ))
        positive = any(term in combined for term in (
            "警示函", "监管谈话", "监管关注", "关注函", "被罚", "罚款",
            "事故", "问询函", "进行中", "占用", "故障", "主动维权", "作为原告",
        ))
        if negative and not positive:
            continue
        if combined.strip() in {"—", "-"}:
            continue
        if any(term in combined for term in ("作为原告", "主动维权", "胜诉", "非处罚", "问询函", "轻微")):
            level = "LOW"
        elif any(term in combined for term in ("被列为被执行", "重大违法失信", "刑事处罚", "公司作为被告")):
            level = "HIGH"
        elif any(term in combined for term in ("被罚", "罚款", "警示", "关注", "事故", "诉讼")):
            level = "MEDIUM"
        else:
            level = "LOW"
        source = _clean(row[3]) if len(row) > 3 else source_title
        digest = hashlib.sha256(f"{enterprise_id}|{label}|{detail}".encode("utf-8")).hexdigest()[:16]
        events.append({
            "event_id": f"PARK-{digest.upper()}",
            "enterprise_id": enterprise_id,
            "event_type": event_type,
            "event_level": level,
            "title": _clean(label),
            "description": _clean(detail) or _clean(status),
            "occurred_date": None,
            "source": source or source_title,
            "source_url": None,
            "data_source": "park_document",
            "confidence_score": 0.75,
            "evidence": [{
                "type": "park_private_document",
                "value": source_title,
                "url": "",
                "document_id": document_id,
            }],
        })
    return events


def extract_document_structure(
    text: str,
    *,
    category: str,
    source_title: str,
    document_id: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Extract explicit enterprise records and risk rows from Markdown text."""
    collected_at = created_at or datetime.now(timezone.utc).isoformat()
    enterprises: list[dict[str, Any]] = []
    sections = _sections(text)
    known_names = {name for name, _body in sections}
    sections.extend(
        (name, body) for name, body in _wide_table_sections(text)
        if name not in known_names
    )
    for name, body in sections:
        rows = _table_rows(body)
        fields = {
            key: _row_value(rows, aliases)
            for key, aliases in FIELD_ALIASES.items()
        }
        # Some reports use a prose subsection for the business scope.
        if not fields["business_scope"]:
            scope = re.search(
                r"(?ms)^###\s+[^\n]*经营范围[^\n]*\n+(.+?)(?=^###\s+|^##\s+|\Z)",
                body,
            )
            if scope:
                fields["business_scope"] = _clean(scope.group(1).splitlines()[0])

        credit = re.sub(r"\s+", "", fields["credit_code"] or "").upper() or None
        identity = credit or re.sub(r"\s+", "", name)
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16].upper()
        enterprise_id = f"ENT-CC-{credit}" if credit else f"ENT-NAME-{digest}"
        # Prefer the explicit business scope when present.  Searching an
        # entire report section would misclassify a piano manufacturer merely
        # because a source note mentions an information system.
        industry, tags = _industry(name, fields["business_scope"] or body)
        capital_text = fields["registered_capital"]
        employee_count = _number(fields["employee_count"])
        patent_count = _number(fields["patent_count"])
        explicit_count = sum(value not in (None, "") for value in fields.values())
        confidence = min(0.9, 0.55 + explicit_count * 0.035 + (0.08 if "http" in body else 0))
        record = {
            "name": name,
            "credit_code": credit,
            "legal_representative": fields["legal_representative"],
            "capital_amount": _number(capital_text, capital=True),
            "capital_currency": "人民币" if capital_text and ("元" in capital_text or "人民币" in capital_text) else None,
            "establishment_date": fields["establishment_date"],
            "registered_address": fields["registered_address"],
            "city": "广州" if "广州" in (fields["registered_address"] or body[:600]) else None,
            "industry": industry,
            "industry_std": None,
            "industry_confidence": round(confidence, 2),
            "enterprise_type": fields["enterprise_type"],
            "enterprise_status": fields["enterprise_status"],
            "business_scope": fields["business_scope"],
            "employee_count": int(employee_count) if employee_count is not None else None,
            "patent_count": int(patent_count) if patent_count is not None else None,
            "website": fields["website"],
            "tags": list(dict.fromkeys(tags + [category, "园区资料导入"])),
            "_meta": {
                "source_title": source_title,
                "source_url": "",
                "collected_at": collected_at,
                "collected_by": "园区资料库结构化解析",
                "document_id": document_id,
                "category": category,
            },
        }
        record["_risk_events"] = _risk_events(
            rows,
            enterprise_id=enterprise_id,
            source_title=source_title,
            document_id=document_id,
        )
        enterprises.append(record)

    return {
        "version": "park-document-structure-v1",
        "document_id": document_id,
        "source_title": source_title,
        "category": category,
        "enterprise_count": len(enterprises),
        "risk_event_count": sum(len(item.get("_risk_events", [])) for item in enterprises),
        "enterprises": enterprises,
    }
