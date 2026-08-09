"""Policy applicability classification used by management and matching APIs.

The policy crawler also collects consultations, result notices and procurement
announcements.  Those documents remain searchable evidence, but they must not
be presented as enterprise application programmes.
"""
from __future__ import annotations

import re
from typing import Any, Literal


PolicyApplicabilityMode = Literal[
    "ELIGIBILITY",
    "REFERENCE_ONLY",
    "UNCLASSIFIED",
]

_REFERENCE_PATTERNS = (
    r"征求.{0,8}意见",
    r"废止|失效",
    r"名单.{0,6}公示|公示.{0,6}名单",
    r"结果.{0,6}公示|评审.{0,6}结果|拟.{0,4}名单",
    r"中标|成交公告|政府采购",
    r"遴选.{0,12}(承担|承办|服务)单位",
    r"政策解读|新闻发布|工作动态",
)

_ELIGIBILITY_PATTERNS = (
    r"申报|申请|申领",
    r"公开征集|项目征集",
    r"补助|补贴|奖励|资助|扶持资金",
    r"认定|入库",
    r"申报指南|实施办法|政策措施",
    r"申报条件|申报对象|支持对象|申请条件",
    r"补助标准|补贴标准|奖励标准|资助标准",
)


def classify_policy_applicability(policy: Any) -> tuple[PolicyApplicabilityMode, str]:
    """Classify whether one catalog document supports enterprise matching."""

    title = str(getattr(policy, "title", "") or "").strip()
    content = str(getattr(policy, "content", "") or "")[:12000]
    searchable_text = f"{title}\n{content}"
    status = str(getattr(policy, "status", "") or "").lower()
    if status in {"inactive", "expired", "abolished", "deleted"}:
        return "REFERENCE_ONLY", "政策已失效或废止，仅保留检索和追溯"
    if any(re.search(pattern, title) for pattern in _REFERENCE_PATTERNS):
        return "REFERENCE_ONLY", "该文件属于公示、征求意见、采购或结果类资料，不进行企业资格匹配"
    if any(re.search(pattern, searchable_text) for pattern in _ELIGIBILITY_PATTERNS):
        return "ELIGIBILITY", "该文件包含申报、认定、补助或政策措施，可进行企业资格预匹配"
    return "UNCLASSIFIED", "尚未识别为可申报政策，仅作为政策资料检索"
