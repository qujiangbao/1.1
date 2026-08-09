"""Search policy Markdown collected by the local Crawl4AI government crawler."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_ALLOWED_GOVERNMENT_DOMAINS = {
    "gz.gov.cn",
    "gzns.gov.cn",
    "haizhu.gov.cn",
    "huadu.gov.cn",
    "panyu.gov.cn",
    "zc.gov.cn",
}

_DOMAIN_TERMS = (
    "机器人", "人工智能", "智能制造", "新能源", "新材料", "集成电路",
    "生物医药", "数字化", "科技", "中小企业", "专精特新", "补贴",
    "扶持", "招商", "产业", "企业", "营商环境", "广州",
)

_GENERIC_MATCH_TERMS = {
    "广州", "广州市", "企业", "产业", "政策", "申报", "扶持", "产业扶持",
}


@dataclass(frozen=True)
class CrawledPolicy:
    policy_id: str
    title: str
    content: str
    source_url: str
    document_number: str = ""
    department: str = ""
    effective_date: str = ""
    expire_date: str = ""
    status: str = ""
    file_size: int = 0
    filename: str = ""
    content_hash: str = ""
    publish_date: str = ""
    source_key: str = ""
    source_name: str = ""
    level: str = "municipal"
    region: str = "广州市"
    document_type: str = "policy"
    deadlines: tuple[str, ...] = ()
    funding_available: bool = False
    parser: str = "baseline"
    parser_version: str = ""
    parse_status: str = ""
    input_sha256: str = ""
    selected_artifact: str = ""

    @property
    def searchable_text(self) -> str:
        return " ".join((
            self.title,
            self.document_number,
            self.department,
            self.content,
        )).lower()


class PolicyCrawl4AIData:
    """Read and rank the versioned cache produced by ``gz_gov_crawler.py``."""

    def __init__(self, data_dir: str | Path | None = None):
        if data_dir is None:
            from app.config import get_settings
            data_dir = get_settings().policy_crawl_data_dir

        configured = Path(data_dir).expanduser()
        if not configured.is_absolute():
            backend_root = Path(__file__).resolve().parents[3]
            configured = backend_root / configured
        self.snapshot_root = configured.resolve()
        self.data_dir = self._resolve_data_dir(self.snapshot_root)
        legacy_index = self.data_dir / "_index.json"
        clean_manifest = self.data_dir / "_clean_manifest.json"
        self.index_path = legacy_index if legacy_index.is_file() else clean_manifest
        self.catalog_path = self.data_dir / "_catalog.json"
        self.report_path = self.data_dir / "_clean_report.json"
        self._documents: list[CrawledPolicy] | None = None
        self._index_mtime_ns: int | None = None

    def search(
        self,
        query: str = "",
        filters: Optional[dict] = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        documents = self._load_documents()
        filters = filters or {}
        terms = self._query_terms(query, filters)

        ranked: list[tuple[float, CrawledPolicy]] = []
        for document in documents:
            if not self._matches_filters(document, filters):
                continue
            score = self._score(document, terms)
            if terms and score <= 0:
                continue
            ranked.append((score, document))

        ranked.sort(
            key=lambda item: (
                item[0],
                item[1].effective_date,
                item[1].policy_id,
            ),
            reverse=True,
        )

        chunks = []
        for index, (raw_score, document) in enumerate(ranked[:max(1, top_k)]):
            score = min(0.98, 0.5 + raw_score / 200) if terms else max(0.5, 0.8 - index * 0.02)
            chunks.append({
                "chunk_id": f"{document.policy_id}-crawl",
                "policy_id": document.policy_id,
                "chunk_index": 0,
                "content": self._excerpt(document.content, terms),
                "score": round(score, 4),
                "search_method": "crawl4ai_keyword",
                "metadata": {
                    "title": document.title,
                    "level": document.level,
                    "department": document.department,
                    "region": document.region,
                    "region_scope": (
                        ["广州市"]
                        if document.region == "广州市"
                        else ["广州市", document.region]
                    ),
                    "document_number": document.document_number,
                    "effective_date": document.effective_date,
                    "expire_date": document.expire_date,
                    "status": document.status,
                    "source_url": document.source_url,
                    "source_type": "crawl4ai_cache",
                    "source_key": document.source_key,
                    "source_name": document.source_name,
                    "document_type": document.document_type,
                    "deadlines": list(document.deadlines),
                    "funding_available": document.funding_available,
                    "parser": document.parser,
                    "parser_version": document.parser_version,
                    "parse_status": document.parse_status,
                    "input_sha256": document.input_sha256,
                    "selected_artifact": document.selected_artifact,
                    "matched_terms": self._matched_terms(document, terms),
                },
                "evidence": [{
                    "type": "government_policy",
                    "value": document.document_number or document.title,
                    "url": document.source_url,
                    "parser": document.parser,
                    "artifact": document.selected_artifact,
                }],
            })
        return chunks

    def stats(self) -> dict[str, Any]:
        documents = self._load_documents()
        report: dict[str, Any] = {}
        if self.report_path.is_file():
            try:
                payload = json.loads(self.report_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    report = payload
            except (OSError, json.JSONDecodeError):
                pass
        updated_at = None
        if self.index_path.exists():
            updated_at = datetime.fromtimestamp(
                self.index_path.stat().st_mtime,
                timezone.utc,
            ).isoformat()
        return {
            "total_documents": len(documents),
            "last_updated": updated_at,
            "data_dir": str(self.data_dir),
            "healthy": bool(documents),
            "raw_records": report.get("raw_records"),
            "included_records": report.get("included_records", len(documents)),
            "failed_records": report.get("failed_records"),
            "with_deadline": report.get(
                "with_deadline", sum(bool(item.deadlines) for item in documents)
            ),
            "with_funding": report.get(
                "with_funding", sum(item.funding_available for item in documents)
            ),
            "published_today": sum(
                item.publish_date == date.today().isoformat() for item in documents
            ),
            "document_types": report.get("document_types", {}),
        }

    def documents(self) -> list[CrawledPolicy]:
        """Return validated documents for ingestion jobs."""
        return list(self._load_documents())

    def catalog_payload(self) -> dict[str, Any]:
        """Return a validated single-file catalog for fast runtime loading."""
        index_bytes = self.index_path.read_bytes()
        return {
            "version": 3,
            "index_sha256": hashlib.sha256(index_bytes).hexdigest(),
            "documents": [asdict(document) for document in self._load_documents()],
        }

    def _load_documents(self) -> list[CrawledPolicy]:
        if not self.index_path.is_file():
            raise FileNotFoundError(f"Crawl4AI policy index not found: {self.index_path}")

        mtime_ns = self.index_path.stat().st_mtime_ns
        if self._documents is not None and self._index_mtime_ns == mtime_ns:
            return self._documents

        index_bytes = self.index_path.read_bytes()
        try:
            entries = json.loads(index_bytes.decode("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid Crawl4AI policy index: {self.index_path}") from exc
        if not isinstance(entries, list):
            raise ValueError("Crawl4AI policy index must contain a JSON array")

        catalog_documents = self._load_catalog(hashlib.sha256(index_bytes).hexdigest())
        if catalog_documents is not None:
            self._documents = catalog_documents
            self._index_mtime_ns = mtime_ns
            logger.info(
                "Loaded %d Crawl4AI government policies from catalog %s",
                len(catalog_documents),
                self.catalog_path,
            )
            return catalog_documents

        documents: list[CrawledPolicy] = []
        for entry in entries:
            document = self._load_entry(entry)
            if document is not None:
                documents.append(document)

        if not documents:
            raise ValueError(f"Crawl4AI policy cache contains no valid documents: {self.data_dir}")

        self._documents = documents
        self._index_mtime_ns = mtime_ns
        logger.info("Loaded %d Crawl4AI government policies from %s", len(documents), self.data_dir)
        return documents

    def _load_catalog(self, index_sha256: str) -> list[CrawledPolicy] | None:
        if not self.catalog_path.is_file():
            return None
        try:
            payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            if (
                payload.get("version") not in (1, 2, 3)
                or payload.get("index_sha256") != index_sha256
                or not isinstance(payload.get("documents"), list)
            ):
                return None
            documents = [CrawledPolicy(**item) for item in payload["documents"]]
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Ignoring invalid Crawl4AI catalog %s: %s", self.catalog_path, exc)
            return None

        valid_documents = [
            document for document in documents
            if self._is_allowed_source_url(document.source_url)
        ]
        return valid_documents or None

    def _load_entry(self, entry: Any) -> CrawledPolicy | None:
        if not isinstance(entry, dict):
            return None
        if entry.get("relevant", True) is False:
            return None
        if entry.get("included") is False:
            return None
        source_url = str(entry.get("url", "")).strip()
        baseline_filename = str(
            entry.get("clean_file") or entry.get("file") or ""
        ).strip()
        selected_filename = str(entry.get("selected_artifact_path") or "").strip()
        preferred_parser = str(entry.get("parser") or "baseline").strip()
        filenames = []
        if entry.get("selected_artifact") == "docling" and selected_filename:
            filenames.append((selected_filename, preferred_parser or "docling"))
        if baseline_filename:
            filenames.append((baseline_filename, "baseline"))
        if not self._is_allowed_source_url(source_url) or not filenames:
            logger.warning("Skipping invalid Crawl4AI policy entry: %r", entry)
            return None

        candidate = None
        actual_parser = "baseline"
        selected_relative = ""
        for filename, parser in filenames:
            possible = (self.data_dir / filename).resolve()
            try:
                possible.relative_to(self.data_dir)
            except ValueError:
                logger.warning("Skipping Crawl4AI path outside cache: %s", filename)
                continue
            if possible.is_file() and possible.stat().st_size <= 2_000_000:
                candidate = possible
                actual_parser = parser
                selected_relative = filename
                break
        if candidate is None:
            return None

        raw = candidate.read_text(encoding="utf-8", errors="replace")
        content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        title_match = re.search(r"^# (?!来源\s*:)(.+?)\s*$", raw, re.MULTILINE)
        entry_title = self._clean_inline(str(entry.get("title") or ""))
        if not title_match and not entry_title:
            logger.warning("Skipping policy without title: %s", candidate)
            return None

        title = entry_title or self._clean_inline(title_match.group(1))
        content = raw[title_match.start():].strip() if title_match else raw.strip()
        policy_id_match = re.search(r"post_(\d+)", source_url)
        source_key = str(entry.get("source_key", "")).strip()
        policy_id = self._policy_id(
            source_key,
            policy_id_match.group(1) if policy_id_match else "",
            candidate,
        )

        return CrawledPolicy(
            policy_id=policy_id,
            title=title,
            content=content,
            source_url=source_url,
            document_number=(
                self._clean_inline(str(entry.get("document_number") or ""))
                or self._metadata(raw, "文号")
            ),
            department=(
                self._clean_inline(str(entry.get("department") or ""))
                or self._metadata(raw, "发布机关")
            ),
            effective_date=self._metadata(raw, "实施日期"),
            expire_date=self._metadata(raw, "失效日期"),
            status=self._metadata(raw, "文件状态"),
            file_size=candidate.stat().st_size,
            filename=candidate.name,
            content_hash=content_hash,
            publish_date=(
                self._clean_inline(str(entry.get("publish_date") or ""))
                or self._metadata(raw, "发布日期")
                or self._metadata(raw, "成文日期")
            ),
            source_key=source_key,
            source_name=str(entry.get("source_name", "")).strip(),
            level=str(entry.get("level", "municipal")).strip() or "municipal",
            region=str(entry.get("region", "广州市")).strip() or "广州市",
            document_type=str(entry.get("document_type", "policy")).strip() or "policy",
            deadlines=tuple(
                str(value).strip()
                for value in entry.get("deadline_dates", entry.get("deadlines", []))
                if str(value).strip()
            ),
            funding_available=bool(entry.get("funding_available", False)),
            parser=actual_parser,
            parser_version=(
                str(entry.get("parser_version") or "").strip()
                if actual_parser == "docling"
                else ""
            ),
            parse_status=str(entry.get("parse_status") or "").strip(),
            input_sha256=str(entry.get("input_sha256") or "").strip(),
            selected_artifact=selected_relative,
        )

    @staticmethod
    def _resolve_data_dir(configured: Path) -> Path:
        """Accept either a legacy cache, one snapshot, or a snapshot root."""
        if (
            (configured / "_index.json").is_file()
            or (configured / "_clean_manifest.json").is_file()
        ):
            return configured
        if not configured.is_dir():
            return configured
        valid_children = [
            child
            for child in configured.iterdir()
            if child.is_dir()
            and (child / "_clean_manifest.json").is_file()
            and (child / "clean").is_dir()
        ]
        canonical = [
            child for child in valid_children if child.name.startswith("snapshot-")
        ]
        candidates = sorted(
            canonical or valid_children,
            key=lambda child: (child.name, child.stat().st_mtime_ns),
            reverse=True,
        )
        return candidates[0] if candidates else configured

    @staticmethod
    def _is_allowed_source_url(url: str) -> bool:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        return parsed.scheme == "https" and any(
            host == domain or host.endswith(f".{domain}")
            for domain in _ALLOWED_GOVERNMENT_DOMAINS
        )

    @staticmethod
    def _policy_id(source_key: str, post_id: str, candidate: Path) -> str:
        if not post_id:
            return candidate.stem.upper()
        prefixes = {
            "": "GZ-FG",
            "gz_fgw": "GZ-FG",
            "gz_gxj": "GZ-GXJ",
            "gz_kjj": "GZ-KJJ",
            "gz_swj": "GZ-SWJ",
            "hp_department": "GZ-HP-DEPT",
            "hp_government": "GZ-HP-GOV",
        }
        prefix = prefixes.get(
            source_key,
            f"GZ-{source_key.upper().replace('_', '-')}",
        )
        return f"{prefix}-{post_id}"

    @staticmethod
    def _metadata(raw: str, label: str) -> str:
        flexible_label = r"\s*".join(re.escape(character) for character in label)
        match = re.search(rf"{flexible_label}\s*[：:]\s*([^\r\n]+)", raw)
        return PolicyCrawl4AIData._clean_inline(match.group(1)) if match else ""

    @staticmethod
    def _clean_inline(value: str) -> str:
        value = re.sub(r"[*_`]+", "", value)
        return re.sub(r"\s+", " ", value).strip(" |")

    @staticmethod
    def _query_terms(query: str, filters: dict) -> list[str]:
        combined = " ".join((
            query,
            str(filters.get("industry", "")),
            str(filters.get("department", "")),
        )).lower()
        terms = {
            item.strip()
            for item in re.split(r"[\s,，。；;、/]+", combined)
            if len(item.strip()) >= 2
        }
        terms.update(term for term in _DOMAIN_TERMS if term in combined)
        return sorted(terms, key=len, reverse=True)

    @staticmethod
    def _matches_filters(document: CrawledPolicy, filters: dict) -> bool:
        level = str(filters.get("level", "")).strip()
        if level and level != document.level:
            return False
        region = str(filters.get("region", "")).lower()
        if (
            region
            and region not in document.region.lower()
            and document.region.lower() not in region
            and region not in ("广州", "广州市")
        ):
            return False
        department = str(filters.get("department", "")).lower()
        if department and department not in document.department.lower():
            return False
        if filters.get("active_only") is not False:
            if document.status and document.status not in ("有效", "现行有效"):
                return False
            if document.expire_date:
                try:
                    if date.fromisoformat(document.expire_date) < date.today():
                        return False
                except ValueError:
                    pass
        return True

    @staticmethod
    def _score(document: CrawledPolicy, terms: list[str]) -> float:
        if not terms:
            return 0
        title = document.title.lower()
        metadata = f"{document.document_number} {document.department}".lower()
        body = document.content.lower()
        score = 0.0
        for term in terms:
            weight = 0.2 if term in {"广州", "广州市", "企业", "产业", "政策"} else 1.0
            if term in title:
                score += 18 * weight
            if term in metadata:
                score += 8 * weight
            score += min(body.count(term), 8) * 1.5 * weight
        return score

    @staticmethod
    def _matched_terms(document: CrawledPolicy, terms: list[str]) -> list[str]:
        searchable = document.searchable_text
        matched = [term for term in terms if term in searchable]
        specific = [term for term in matched if term not in _GENERIC_MATCH_TERMS]
        return (specific or matched)[:6]

    @staticmethod
    def _excerpt(content: str, terms: list[str], max_length: int = 500) -> str:
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)
        text = re.sub(r"[#>*_`|]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        positions = [text.lower().find(term) for term in terms if text.lower().find(term) >= 0]
        start = max(0, min(positions) - 100) if positions else 0
        excerpt = text[start:start + max_length].strip()
        if start:
            excerpt = f"…{excerpt}"
        if start + max_length < len(text):
            excerpt = f"{excerpt}…"
        return excerpt
