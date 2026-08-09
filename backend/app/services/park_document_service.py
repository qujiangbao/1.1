"""Persistent, lightweight document library owned by the park.

Files and extracted text live on a Docker volume.  The implementation avoids
holding a second database/vector service in memory, which is important on the
2 GB deployment; keyword relevance makes imported material immediately
searchable and reviewable.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from threading import RLock
from typing import Any
from uuid import uuid4

from app.services.document_parser import DocumentParser


LIBRARY_ROOT = Path("data/park_documents")
INDEX_PATH = LIBRARY_ROOT / "index.json"
FILES_DIR = LIBRARY_ROOT / "files"
TEXT_DIR = LIBRARY_ROOT / "text"
STRUCTURED_DIR = LIBRARY_ROOT / "structured"
ALLOWED_SUFFIXES = {".pdf", ".docx", ".pptx", ".txt", ".md"}
ALLOWED_CATEGORIES = {
    "园区规划", "招商资料", "企业资料", "政策文件", "会议纪要", "园区综合资料",
}
QUERY_STOP_TERMS = {
    "请问", "一下", "哪些", "什么", "如何", "怎么", "有没有", "相关",
    "资料", "资料库", "园区", "查询", "检索", "有哪", "一下子",
    "园区资料库查询", "园区资料库检索",
}
_INDEX_LOCK = RLock()


def _ensure_dirs() -> None:
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    STRUCTURED_DIR.mkdir(parents=True, exist_ok=True)


def _content_hash(text: str) -> str:
    normalized = re.sub(r"[\W_]+", "", text.lower(), flags=re.UNICODE)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _is_policy_material(record: dict[str, Any]) -> bool:
    category = str(record.get("category") or "").strip()
    if category == "政策文件":
        return True
    if category == "企业资料":
        return False
    labels = " ".join([
        str(record.get("name") or ""),
        *[str(item) for item in record.get("tags", [])],
    ])
    return "政策" in labels or "申报" in labels


def _matches_purpose(record: dict[str, Any], purpose: str | None) -> bool:
    if not purpose or purpose == "all":
        return True
    if purpose == "policy":
        return _is_policy_material(record)
    if purpose == "enterprise":
        return str(record.get("category") or "") in {"企业资料", "招商资料", "园区综合资料"}
    return True


def _write_structured_payload(record: dict[str, Any], text: str) -> dict[str, Any]:
    from app.services.park_document_structuring import extract_document_structure

    payload = extract_document_structure(
        text,
        category=str(record.get("category") or "园区综合资料"),
        source_title=str(record.get("name") or "园区资料"),
        document_id=str(record["id"]),
        created_at=str(record.get("created_at") or ""),
    )
    (STRUCTURED_DIR / f"{record['id']}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def list_structured_enterprise_records() -> list[dict[str, Any]]:
    """Return explicit enterprise facts extracted from park-owned documents.

    Existing documents are indexed lazily so an upgrade immediately activates
    material already present in the persistent volume.
    """
    output: list[dict[str, Any]] = []
    with _INDEX_LOCK:
        for record in _load_index():
            if record.get("status") != "READY" or not _matches_purpose(record, "enterprise"):
                continue
            structured_path = STRUCTURED_DIR / f"{record['id']}.json"
            try:
                if structured_path.exists():
                    payload = json.loads(structured_path.read_text(encoding="utf-8"))
                else:
                    text_path = TEXT_DIR / f"{record['id']}.txt"
                    if not text_path.exists():
                        continue
                    payload = _write_structured_payload(
                        record,
                        text_path.read_text(encoding="utf-8", errors="ignore"),
                    )
                output.extend(
                    item for item in payload.get("enterprises", [])
                    if isinstance(item, dict) and item.get("name")
                )
            except (OSError, ValueError, json.JSONDecodeError):
                continue
    return output


def _load_index() -> list[dict[str, Any]]:
    with _INDEX_LOCK:
        _ensure_dirs()
        if not INDEX_PATH.exists():
            return []
        try:
            payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            return payload if isinstance(payload, list) else []
        except (OSError, json.JSONDecodeError):
            return []


def _save_index(items: list[dict[str, Any]]) -> None:
    with _INDEX_LOCK:
        _ensure_dirs()
        temporary = INDEX_PATH.with_suffix(f".{uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(INDEX_PATH)


def list_park_documents() -> list[dict[str, Any]]:
    with _INDEX_LOCK:
        items = _load_index()
        changed = False
        for record in items:
            if record.get("status") != "READY":
                continue
            structured_path = STRUCTURED_DIR / f"{record['id']}.json"
            if (
                structured_path.exists()
                and "structured_enterprises" in record
                and "structured_risk_events" in record
            ):
                continue
            text_path = TEXT_DIR / f"{record['id']}.txt"
            if not text_path.exists():
                continue
            try:
                payload = _write_structured_payload(
                    record,
                    text_path.read_text(encoding="utf-8", errors="ignore"),
                )
                record["structured_enterprises"] = payload.get("enterprise_count", 0)
                record["structured_risk_events"] = payload.get("risk_event_count", 0)
                changed = True
            except (OSError, ValueError):
                continue
        if changed:
            _save_index(items)
    return sorted(items, key=lambda item: item["created_at"], reverse=True)


async def import_park_document(
    source_path: Path,
    *,
    original_name: str,
    category: str,
    tags: list[str],
    created_by: str,
) -> dict[str, Any]:
    _ensure_dirs()
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("仅支持 PDF、DOCX、PPTX、TXT 和 Markdown 文件")
    category = category.strip() or "园区综合资料"
    if category not in ALLOWED_CATEGORIES:
        raise ValueError("资料分类无效，请从系统支持的分类中选择")

    parsed = await DocumentParser().parse(str(source_path))
    if not parsed.is_valid:
        raise ValueError(parsed.error or "文档无法解析")
    normalized_hash = _content_hash(parsed.raw_text)
    with _INDEX_LOCK:
        items = _load_index()
        for existing in items:
            existing_content_hash = existing.get("content_hash")
            if not existing_content_hash:
                existing_text = TEXT_DIR / f"{existing.get('id')}.txt"
                if existing_text.exists():
                    existing_content_hash = _content_hash(
                        existing_text.read_text(encoding="utf-8", errors="ignore")
                    )
            if (
                existing.get("status") == "READY"
                and (
                    existing.get("file_hash") == parsed.file_hash
                    or existing_content_hash == normalized_hash
                )
            ):
                return {**existing, "duplicate": True, "duplicate_of": existing.get("id")}

        document_id = str(uuid4())
        stored_path = FILES_DIR / f"{document_id}{suffix}"
        shutil.move(str(source_path), stored_path)
        text_path = TEXT_DIR / f"{document_id}.txt"
        if parsed.raw_text:
            text_path.write_text(parsed.raw_text, encoding="utf-8")

        record = {
            "id": document_id,
            "name": original_name,
            "category": category,
            "tags": tags,
            "format": suffix.lstrip(".").upper(),
            "file_size": parsed.file_size or stored_path.stat().st_size,
            "page_count": parsed.page_count,
            "file_hash": parsed.file_hash,
            "content_hash": normalized_hash,
            "status": "READY" if parsed.is_valid else "FAILED",
            "error": parsed.error,
            "text_length": len(parsed.raw_text),
            "excerpt": parsed.raw_text[:260].replace("\n", " ") if parsed.raw_text else "",
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        structured = _write_structured_payload(record, parsed.raw_text)
        record["structured_enterprises"] = structured.get("enterprise_count", 0)
        record["structured_risk_events"] = structured.get("risk_event_count", 0)
        items.append(record)
        _save_index(items)
    return record


def delete_park_document(document_id: str) -> bool:
    with _INDEX_LOCK:
        items = _load_index()
        record = next((item for item in items if item.get("id") == document_id), None)
        if record is None:
            return False
        suffix = "." + str(record.get("format", "")).lower()
        (FILES_DIR / f"{document_id}{suffix}").unlink(missing_ok=True)
        (TEXT_DIR / f"{document_id}.txt").unlink(missing_ok=True)
        (STRUCTURED_DIR / f"{document_id}.json").unlink(missing_ok=True)
        _save_index([item for item in items if item.get("id") != document_id])
        return True


def _query_terms(query: str) -> list[str]:
    """Tokenize mixed Chinese/Latin queries without adding a heavy segmenter.

    The original implementation treated a natural Chinese sentence as one
    exact term, so a query such as“启航智造产业园有哪些招商目标”could not
    match a document containing those concepts in separate sentences. Keep
    short phrases intact and add 2-4 character n-grams for longer Chinese
    runs. Common question words are ignored to reduce accidental matches.
    """
    terms: list[str] = []
    for segment in re.findall(r"[a-zA-Z0-9_-]{2,}|[\u4e00-\u9fff]+", query.lower()):
        if segment in QUERY_STOP_TERMS:
            continue
        if re.fullmatch(r"[a-zA-Z0-9_-]{2,}", segment):
            terms.append(segment)
            continue
        if 2 <= len(segment) <= 4:
            terms.append(segment)
            continue
        terms.append(segment)
        for size in (2, 3, 4):
            terms.extend(
                segment[index:index + size]
                for index in range(len(segment) - size + 1)
            )
    return list(dict.fromkeys(
        term for term in terms
        if len(term) >= 2 and term not in QUERY_STOP_TERMS
    ))[:80]


def search_park_documents(
    query: str,
    top_k: int = 5,
    *,
    purpose: str | None = None,
) -> list[dict[str, Any]]:
    terms = _query_terms(query)
    if not terms:
        return []
    ranked: list[tuple[float, dict[str, Any], str]] = []
    with _INDEX_LOCK:
        for record in _load_index():
            if record.get("status") != "READY":
                continue
            if not _matches_purpose(record, purpose):
                continue
            text_path = TEXT_DIR / f"{record['id']}.txt"
            if not text_path.exists():
                continue
            text = text_path.read_text(encoding="utf-8", errors="ignore")
            haystack = f"{record.get('name', '')} {' '.join(record.get('tags', []))} {text}".lower()
            matched_terms = [term for term in terms if term in haystack]
            hit_count = sum(haystack.count(term) for term in matched_terms)
            if hit_count <= 0:
                continue
            first_positions = [haystack.find(term) for term in terms if haystack.find(term) >= 0]
            start = max(0, (min(first_positions) if first_positions else 0) - 100)
            snippet = text[start:start + 900]
            coverage = len(matched_terms) / max(1, len(terms))
            score = min(0.99, 0.45 + coverage * 0.45 + min(0.09, hit_count / 100))
            ranked.append((score, record, snippet))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "chunk_id": f"park-doc-{record['id']}",
            "policy_id": f"park-doc-{record['id']}",
            "chunk_index": 0,
            "title": record["name"],
            "content": snippet,
            "content_snippet": snippet[:360],
            "score": round(score, 4),
            "match_score": round(score * 100, 1),
            "search_method": "park_document_keyword",
            "source_url": None,
            "metadata": {
                "source_title": record["name"],
                "source_type": "park_private_document",
                "category": record["category"],
                "tags": record["tags"],
                "document_id": record["id"],
            },
            "evidence": [{
                "type": "park_private_document",
                "value": f"园区上传资料：{record['name']}",
                "url": "",
            }],
        }
        for score, record, snippet in ranked[:top_k]
    ]
