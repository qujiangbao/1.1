"""Conservative extraction of eligibility-rule drafts from policy source text.

The extractor only emits a rule when one source sentence contains both an
enterprise field and an explicit comparison value. Every result stays DRAFT
until a policy manager checks it against the original document.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any


def _sentences(text: str) -> list[str]:
    normalized = re.sub(r"[\t\r]+", " ", text or "")
    normalized = re.sub(r"[ ]{2,}", " ", normalized)
    return [
        item.strip(" \n-•")
        for item in re.split(r"(?<=[。；;！？!?])|\n+", normalized)
        if 8 <= len(item.strip()) <= 1000
    ]


def _code(field: str, source_text: str) -> str:
    digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()[:10].upper()
    return f"SOURCE_{field.upper()}_{digest}"


def _draft(
    *, field: str, label: str, operator: str, expected_value: Any, source_text: str
) -> dict[str, Any]:
    return {
        "condition_code": _code(field, source_text),
        "label": label,
        "field": field,
        "operator": operator,
        "expected_value": expected_value,
        "mandatory": True,
        "review_status": "DRAFT",
        "source_text": source_text,
    }


def extract_policy_condition_drafts(content: str) -> list[dict[str, Any]]:
    """Return source-backed drafts without guessing missing requirements."""
    drafts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(candidate: dict[str, Any]) -> None:
        key = (
            candidate["field"],
            candidate["operator"],
            str(candidate["expected_value"]),
        )
        if key not in seen:
            drafts.append(candidate)
            seen.add(key)

    for sentence in _sentences(content):
        enterprise_definition = re.search(
            r"本政策措施所称的.{0,30}企业是指从事(.{2,240}?)(?:的相关企业|相关企业)",
            sentence,
        )
        if enterprise_definition:
            scope = enterprise_definition.group(1)
            terms = [
                term for term in (
                    "具身智能机器人", "机器人整机", "核心零部件", "系统集成",
                    "人工智能", "智能制造", "高端装备",
                )
                if term in scope
            ]
            if terms:
                add(_draft(
                    field="industry",
                    label="政策适用产业范围",
                    operator="CONTAINS",
                    expected_value=terms,
                    source_text=sentence,
                ))

        if (
            "广州" in sentence
            and re.search(r"注册地|注册地址|登记注册|依法注册|注册登记", sentence)
            and re.search(r"应当|应在|须|需|要求|条件|对象|范围|企业", sentence)
        ):
            add(_draft(
                field="region",
                label="企业注册地区域",
                operator="CONTAINS",
                expected_value=["广州"],
                source_text=sentence,
            ))

        capital = re.search(
            r"注册资本.{0,20}(?:不低于|不少于|达到|应为|须为)[^\d]{0,8}(\d+(?:\.\d+)?)\s*(亿|万)?元",
            sentence,
        )
        if capital:
            amount = float(capital.group(1)) * (10000 if capital.group(2) == "亿" else 1)
            add(_draft(
                field="capital_amount",
                label="注册资本要求",
                operator="GTE",
                expected_value=amount,
                source_text=sentence,
            ))

        patent = re.search(
            r"(?:发明)?专利.{0,20}(?:不低于|不少于|至少|达到|拥有)[^\d]{0,8}(\d+)\s*(?:项|件)",
            sentence,
        )
        if patent:
            add(_draft(
                field="patents_count",
                label="知识产权数量要求",
                operator="GTE",
                expected_value=int(patent.group(1)),
                source_text=sentence,
            ))

        employees = re.search(
            r"(?:从业人员|职工人数|员工人数|参保人数).{0,20}(?:不低于|不少于|至少|达到)[^\d]{0,8}(\d+)\s*人",
            sentence,
        )
        if employees:
            add(_draft(
                field="employee_count",
                label="企业人员数量要求",
                operator="GTE",
                expected_value=int(employees.group(1)),
                source_text=sentence,
            ))

        if (
            re.search(r"经营状态|登记状态", sentence)
            and re.search(r"存续|在营|正常", sentence)
            and re.search(r"应当|须|需|要求|条件", sentence)
        ):
            values = [value for value in ("存续", "在营", "正常") if value in sentence]
            add(_draft(
                field="enterprise_status",
                label="经营状态要求",
                operator="IN",
                expected_value=values,
                source_text=sentence,
            ))
    return drafts[:100]
