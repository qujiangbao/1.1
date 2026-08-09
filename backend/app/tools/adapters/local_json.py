"""Read-only enterprise adapter for the cleaned local JSON snapshot."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, List

from app.schemas.enterprise import (
    BusinessStatus,
    EnterpriseProfile,
    EnterpriseSearchResult,
    RiskEvent,
)
from app.tools.adapters.base import DataAdapter

_INDUSTRY_LABELS = {
    "ai": "人工智能",
    "biopharma": "生物医药",
    "digital_economy": "数字经济",
    "integrated_circuits": "集成电路",
    "nev": "新能源汽车",
    "robotics": "机器人",
    "semiconductor": "半导体",
    "smart_manufacturing": "智能制造",
}


class LocalJsonAdapter(DataAdapter):
    """Load ``list[dict]`` enterprise data without inventing missing fields."""

    MAX_FILE_SIZE = 50 * 1024 * 1024

    def __init__(
        self,
        data_path: str | Path,
        *,
        include_park_documents: bool = False,
    ):
        configured = Path(data_path).expanduser()
        if not configured.is_absolute():
            backend_root = Path(__file__).resolve().parents[3]
            configured = backend_root / configured
        self.data_path = configured.resolve()
        self.include_park_documents = include_park_documents
        self._records: list[dict[str, Any]] | None = None
        self._by_id: dict[str, dict[str, Any]] = {}
        self._mtime_ns: int | None = None
        self._park_index_mtime_ns: int | None = None
        self._raw_count = 0
        self._risk_by_id: dict[str, list[dict[str, Any]]] = {}

    @property
    def source_name(self) -> str:
        return "local_json"

    async def get_profile(self, enterprise_id: str) -> EnterpriseProfile:
        self._load()
        record = self._by_id.get(enterprise_id)
        if record is None:
            raise KeyError(f"Enterprise not found: {enterprise_id}")
        return self._to_profile(record)

    async def search_enterprises(
        self,
        query: str,
        industry: str = None,
        location: str = None,
        limit: int = 20,
    ) -> EnterpriseSearchResult:
        return await self.search_enterprises_advanced(
            query=query,
            industry=industry,
            location=location,
            limit=limit,
        )

    async def search_enterprises_advanced(
        self,
        query: str = "",
        industry: str | None = None,
        location: str | None = None,
        min_capital: float | None = None,
        max_capital: float | None = None,
        sort_by: str = "relevance",
        limit: int = 20,
    ) -> EnterpriseSearchResult:
        records = self._load()
        query_terms = self._terms(query)
        ranked: list[tuple[float, dict[str, Any], list[str]]] = []

        for record in records:
            capital = self._number(record.get("capital_amount"))
            if min_capital is not None and (capital is None or capital < min_capital):
                continue
            if max_capital is not None and (capital is None or capital > max_capital):
                continue
            if industry and not self._contains(
                " ".join((
                    str(record.get("industry") or ""),
                    str(record.get("industry_std") or ""),
                    self._industry_label(record),
                )),
                industry,
            ):
                continue
            if location and not self._contains(
                f"{record.get('city') or ''} {record.get('registered_address') or ''}",
                location,
            ):
                continue

            score, fields = self._match(record, query_terms)
            if query_terms and score <= 0:
                continue
            ranked.append((score, record, fields))

        if sort_by == "capital_desc":
            ranked.sort(
                key=lambda item: (
                    self._number(item[1].get("capital_amount")) is not None,
                    self._number(item[1].get("capital_amount")) or 0,
                    item[0],
                ),
                reverse=True,
            )
        elif sort_by == "capital_asc":
            ranked.sort(
                key=lambda item: (
                    self._number(item[1].get("capital_amount")) is None,
                    self._number(item[1].get("capital_amount")) or 0,
                    -item[0],
                )
            )
        else:
            ranked.sort(key=lambda item: (item[0], item[1].get("name") or ""), reverse=True)

        enterprises: list[EnterpriseProfile] = []
        for _, record, fields in ranked[:max(1, limit)]:
            profile = self._to_profile(record)
            if fields:
                profile.match_reason = "匹配字段：" + "、".join(fields)
            elif not query_terms:
                profile.match_reason = "企业库浏览结果"
            enterprises.append(profile)

        return EnterpriseSearchResult(
            query=query,
            total=len(ranked),
            enterprises=enterprises,
            data_source=self.source_name,
            confidence_score=1.0,
        )

    async def get_risk_events(
        self,
        enterprise_id: str,
        event_type: str = None,
        limit: int = 20,
    ) -> List[RiskEvent]:
        self._require_record(enterprise_id)
        events = self._risk_by_id.get(enterprise_id, [])
        if event_type:
            events = [item for item in events if item.get("event_type") == event_type]
        return [RiskEvent.model_validate(item) for item in events[:max(1, limit)]]

    async def get_business_status(self, enterprise_id: str) -> BusinessStatus:
        record = self._require_record(enterprise_id)
        raw_status = str(record.get("enterprise_status") or "").strip()
        status = "normal" if raw_status in {"存续", "在业", "开业", "正常"} else "unknown"
        events = self._risk_by_id.get(enterprise_id, [])
        penalties = [
            {
                "reason": item.get("description") or item.get("title"),
                "amount": None,
                "date": item.get("occurred_date"),
                "authority": item.get("source"),
            }
            for item in events
            if item.get("event_type") == "administrative"
        ]
        return BusinessStatus(
            enterprise_id=enterprise_id,
            status=status,
            status_detail=raw_status or "未采集",
            penalties=penalties,
            data_source=self.source_name,
            confidence_score=1.0 if raw_status else 0.0,
            evidence=self._evidence(record),
        )

    async def health_check(self) -> bool:
        try:
            return bool(self._load())
        except (OSError, ValueError, json.JSONDecodeError):
            return False

    def stats(self) -> dict[str, Any]:
        records = self._load()
        total = len(records)
        credit_count = sum(bool(self._credit(item.get("credit_code"))) for item in records)
        patent_count = sum(item.get("patent_count") is not None for item in records)
        capital_count = sum(self._number(item.get("capital_amount")) is not None for item in records)
        park_enterprise_count = sum(
            any(source.get("document_id") for source in item.get("_sources", []) if isinstance(source, dict))
            for item in records
        )
        risk_event_count = sum(len(item.get("_risk_events", [])) for item in records)
        industries = Counter(
            self._industry_label(item)
            for item in records
        )
        return {
            "raw_records": self._raw_count,
            "total_enterprises": total,
            "deduplicated_records": max(0, self._raw_count - total),
            "park_document_enterprises": park_enterprise_count,
            "risk_event_count": risk_event_count,
            "coverage": {
                "credit_code": self._coverage(credit_count, total),
                "patent_count": self._coverage(patent_count, total),
                "capital_amount": self._coverage(capital_count, total),
            },
            "industry_distribution": [
                {"name": name, "value": count}
                for name, count in industries.most_common(8)
            ],
            "data_path": str(self.data_path),
            "last_updated": datetime.fromtimestamp(
                self.data_path.stat().st_mtime, timezone.utc
            ).isoformat(),
            "data_available": total > 0,
            "limitations": [
                "credit_code 缺失时使用规范化企业名称作为去重键",
                "patent_count=null 表示尚未采集，不能解释为 0",
                "园区企业资料可补充风险事件；未导入证据的企业风险仍保持未知",
                "本地快照不包含权威招商签约、转化率或完整融资招聘数据",
            ],
        }

    def risk_overview(self, limit: int = 50) -> dict[str, Any]:
        """Aggregate imported, source-traceable events by enterprise.

        The severity score is a display mapping, not a prediction. Enterprises
        with no imported risk evidence are deliberately left unevaluated.
        """
        records = self._load()
        severity_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
        severity_score = {"LOW": 30.0, "MEDIUM": 60.0, "HIGH": 80.0}
        distribution = {"high": 0, "medium": 0, "low": 0}
        enterprises: list[dict[str, Any]] = []

        for record in records:
            events = [
                item for item in record.get("_risk_events", [])
                if isinstance(item, dict)
                and str(item.get("event_level") or item.get("risk_level") or "").upper()
                in severity_rank
            ]
            if not events:
                continue
            level = max(
                (
                    str(item.get("event_level") or item.get("risk_level") or "").upper()
                    for item in events
                ),
                key=lambda item: severity_rank[item],
            )
            level_key = level.lower()
            distribution[level_key] += 1
            reasons = []
            for event in events:
                reason = str(event.get("description") or event.get("title") or "").strip()
                if reason and reason not in reasons:
                    reasons.append(reason)
            sources = [
                str(item.get("source") or "").strip()
                for item in events
                if str(item.get("source") or "").strip()
            ]
            dates = [
                str(item.get("occurred_date") or "").strip()
                for item in events
                if str(item.get("occurred_date") or "").strip()
            ]
            enterprises.append({
                "enterprise_id": record["_enterprise_id"],
                "name": str(record.get("name") or record["_enterprise_id"]),
                "score": severity_score[level],
                "level": level_key,
                "reason": "；".join(reasons[:3]) or "已导入可核验风险事件",
                "risk_type": "imported_public_evidence",
                "source": "；".join(dict.fromkeys(sources)) or "园区资料库",
                "created_at": max(dates) if dates else None,
                "trend": "unknown",
                "action": "优先人工复核" if level in {"HIGH", "MEDIUM"} else "常规跟踪",
                "event_count": len(events),
                "score_method": "verified_event_severity_mapping",
            })

        enterprises.sort(
            key=lambda item: (
                severity_rank[item["level"].upper()],
                item.get("created_at") or "",
            ),
            reverse=True,
        )
        return {
            "evaluated_enterprises": len(enterprises),
            "distribution": distribution,
            "enterprises": enterprises[:max(1, limit)],
            "source": "park_document_evidence",
        }

    def _load(self) -> list[dict[str, Any]]:
        if not self.data_path.is_file():
            raise FileNotFoundError(f"Enterprise JSON not found: {self.data_path}")
        stat = self.data_path.stat()
        try:
            from app.services.park_document_service import INDEX_PATH

            park_mtime_ns = (
                INDEX_PATH.stat().st_mtime_ns
                if self.include_park_documents and INDEX_PATH.exists()
                else None
            )
        except Exception:
            park_mtime_ns = None
        if stat.st_size > self.MAX_FILE_SIZE:
            raise ValueError(f"Enterprise JSON exceeds {self.MAX_FILE_SIZE} bytes")
        if (
            self._records is not None
            and self._mtime_ns == stat.st_mtime_ns
            and self._park_index_mtime_ns == park_mtime_ns
        ):
            return self._records

        payload = json.loads(self.data_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Enterprise JSON must contain list[dict]")

        park_records: list[dict[str, Any]] = []
        if self.include_park_documents:
            try:
                from app.services.park_document_service import list_structured_enterprise_records

                park_records = list_structured_enterprise_records()
            except Exception:
                park_records = []

        merged: dict[str, dict[str, Any]] = {}
        self._raw_count = len(payload) + len(park_records)
        for item in [*payload, *park_records]:
            if not isinstance(item, dict) or not str(item.get("name") or "").strip():
                continue
            record = dict(item)
            record["_enterprise_id"] = self._enterprise_id(record)
            source_meta = record.get("_meta")
            record["_sources"] = [source_meta] if isinstance(source_meta, dict) else []
            key = self._identity_key(record)
            if key in merged:
                merged[key] = self._merge(merged[key], record)
            else:
                merged[key] = record

        # Merge a sparse name-fallback row into the unique credit-code row
        # when both represent the exact same normalized enterprise name.
        credit_keys_by_name: dict[str, list[str]] = {}
        for key, record in merged.items():
            if key.startswith("credit:"):
                credit_keys_by_name.setdefault(
                    self._normalize(record.get("name")), []
                ).append(key)
        for key, record in list(merged.items()):
            if not key.startswith("name:"):
                continue
            credit_keys = credit_keys_by_name.get(
                self._normalize(record.get("name")), []
            )
            if len(credit_keys) == 1:
                credit_key = credit_keys[0]
                merged[credit_key] = self._merge(merged[credit_key], record)
                del merged[key]

        self._records = list(merged.values())
        self._by_id = {record["_enterprise_id"]: record for record in self._records}
        self._risk_by_id = {
            record["_enterprise_id"]: [
                {**item, "enterprise_id": record["_enterprise_id"]}
                for item in record.get("_risk_events", [])
                if isinstance(item, dict)
            ]
            for record in self._records
        }
        self._mtime_ns = stat.st_mtime_ns
        self._park_index_mtime_ns = park_mtime_ns
        return self._records

    def _require_record(self, enterprise_id: str) -> dict[str, Any]:
        self._load()
        record = self._by_id.get(enterprise_id)
        if record is None:
            raise KeyError(f"Enterprise not found: {enterprise_id}")
        return record

    def _to_profile(self, record: dict[str, Any]) -> EnterpriseProfile:
        capital = self._number(record.get("capital_amount"))
        currency = str(record.get("capital_currency") or "").strip() or None
        registered_capital = None
        if capital is not None:
            registered_capital = f"{capital:,.2f}".rstrip("0").rstrip(".")
            if currency:
                registered_capital = f"{registered_capital} {currency}"

        patent_value = record.get("patent_count")
        patents = int(patent_value) if isinstance(patent_value, (int, float)) else None
        source_meta = record.get("_meta") if isinstance(record.get("_meta"), dict) else {}
        confidence = self._number(record.get("industry_confidence"))
        if confidence is None or not 0 <= confidence <= 1:
            confidence = 1.0

        return EnterpriseProfile(
            enterprise_id=record["_enterprise_id"],
            name=str(record.get("name") or "").strip(),
            credit_code=self._credit(record.get("credit_code")) or None,
            legal_representative=self._text(record.get("legal_representative")),
            registered_capital=registered_capital,
            capital_amount=capital,
            capital_currency=currency,
            established_date=self._text(record.get("establishment_date")),
            company_type=self._text(record.get("enterprise_type")),
            enterprise_status=self._text(record.get("enterprise_status")),
            industry=self._industry_label(record),
            industry_code=self._text(record.get("industry")),
            business_scope=self._text(record.get("business_scope")),
            address=self._text(record.get("registered_address")),
            location=self._text(record.get("city")),
            employee_count=int(record["employee_count"]) if self._number(record.get("employee_count")) is not None else None,
            revenue_level=self._text(record.get("revenue_level")),
            growth_rate=self._number(record.get("growth_rate")),
            funding_stage=self._text(record.get("funding_stage")),
            funding_amount=self._number(record.get("funding_amount")),
            patents_count=patents,
            trademarks_count=int(record["trademarks_count"]) if self._number(record.get("trademarks_count")) is not None else None,
            website=self._text(record.get("website")),
            expansion_willingness=self._text(record.get("expansion_willingness")),
            tags=self._list(record.get("tags")),
            data_quality={
                "identity_key": "credit_code" if self._credit(record.get("credit_code")) else "name",
                "credit_code": "available" if self._credit(record.get("credit_code")) else "missing",
                "patent_count": "available" if patents is not None else "not_collected",
                "capital_amount": "available" if capital is not None else "missing",
                "park_document_sources": len(record.get("_sources", [])),
                "risk_events": len(record.get("_risk_events", [])),
            },
            data_source=self.source_name,
            source_time=self._datetime(source_meta.get("collected_at")),
            confidence_score=float(confidence),
            evidence=self._evidence(record),
        )

    def _evidence(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        meta = record.get("_meta") if isinstance(record.get("_meta"), dict) else {}
        evidence = []
        sources = record.get("_sources") if isinstance(record.get("_sources"), list) else []
        if not sources and meta:
            sources = [meta]
        for source in sources:
            if not isinstance(source, dict) or not (source.get("source_title") or source.get("source_url")):
                continue
            evidence.append({
                "type": "source",
                "value": str(source.get("source_title") or "本地企业数据快照"),
                "url": str(source.get("source_url") or ""),
                "document_id": source.get("document_id"),
            })
        evidence.append({
            "type": "snapshot",
            "value": self.data_path.name,
            "url": "",
        })
        return evidence

    @classmethod
    def _match(cls, record: dict[str, Any], terms: list[str]) -> tuple[float, list[str]]:
        if not terms:
            return 0.0, []
        fields = {
            "企业名称": (str(record.get("name") or ""), 12),
            "行业": (
                (
                    f"{record.get('industry') or ''} "
                    f"{record.get('industry_std') or ''} "
                    f"{cls._industry_label(record)}"
                ),
                8,
            ),
            "经营范围": (str(record.get("business_scope") or ""), 4),
            "标签": (" ".join(cls._list(record.get("tags"))), 6),
            "地区": (
                f"{record.get('city') or ''} {record.get('registered_address') or ''}", 3
            ),
        }
        score = 0.0
        matched = []
        for label, (value, weight) in fields.items():
            normalized = cls._normalize(value)
            count = sum(1 for term in terms if term in normalized)
            if count:
                score += count * weight
                matched.append(label)
        return score, matched

    @classmethod
    def _terms(cls, value: str) -> list[str]:
        return [
            cls._normalize(term)
            for term in re.split(r"[\s,，。；;、/]+", value or "")
            if cls._normalize(term)
        ]

    @classmethod
    def _contains(cls, value: str, expected: str) -> bool:
        return cls._normalize(expected) in cls._normalize(value)

    @staticmethod
    def _industry_label(record: dict[str, Any]) -> str:
        standardized = str(record.get("industry_std") or "").strip()
        if standardized:
            return standardized
        code = str(record.get("industry") or "").strip()
        return _INDUSTRY_LABELS.get(code.lower(), code or "未分类")

    @staticmethod
    def _normalize(value: Any) -> str:
        normalized = unicodedata.normalize("NFKC", str(value or "")).lower()
        return re.sub(r"\s+", "", normalized)

    @classmethod
    def _identity_key(cls, record: dict[str, Any]) -> str:
        credit = cls._credit(record.get("credit_code"))
        return f"credit:{credit}" if credit else f"name:{cls._normalize(record.get('name'))}"

    @classmethod
    def _enterprise_id(cls, record: dict[str, Any]) -> str:
        credit = cls._credit(record.get("credit_code"))
        if credit:
            return f"ENT-CC-{credit}"
        digest = hashlib.sha256(cls._normalize(record.get("name")).encode("utf-8")).hexdigest()
        return f"ENT-NAME-{digest[:16].upper()}"

    @staticmethod
    def _merge(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        merged = dict(existing)
        for list_key in ("_sources", "_risk_events", "tags"):
            combined = []
            for item in [*(existing.get(list_key) or []), *(incoming.get(list_key) or [])]:
                if item not in combined:
                    combined.append(item)
            merged[list_key] = combined
        for key, value in incoming.items():
            if key in {"_sources", "_risk_events", "tags"}:
                continue
            if merged.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
                merged[key] = value
        return merged

    @staticmethod
    def _credit(value: Any) -> str:
        return re.sub(r"\s+", "", str(value or "")).upper()

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _text(value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    @staticmethod
    def _datetime(value: Any) -> datetime:
        if value:
            try:
                return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    @staticmethod
    def _coverage(count: int, total: int) -> dict[str, Any]:
        return {
            "count": count,
            "total": total,
            "rate": round(count / total, 4) if total else 0.0,
        }
