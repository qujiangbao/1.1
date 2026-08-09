"""Project-owned incremental Guangzhou government policy crawler.

The engine only accepts configured ``*.gz.gov.cn`` sources, keeps every fetched
artifact for audit, and marks cross-source copies as aliases instead of deleting
them.  It deliberately contains no authentication or database code; those
boundaries live in the API/service layer.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx


USER_AGENT = "Mozilla/5.0 GuangzhouPolicyAgent/2.0"
HREF_PATTERN = re.compile(r"""href\s*=\s*["']([^"'#]+)["']""", re.I)
TITLE_PATTERN = re.compile(r"^# (?!来源\s*:)(.+?)\s*$", re.MULTILINE)
MAX_WORKERS = 3
MAX_RESPONSE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class PolicySource:
    key: str
    name: str
    list_url: str
    detail_url_regex: str
    level: str
    region: str
    title_keywords: tuple[str, ...] = ()

    def page_url(self, page: int) -> str:
        if page == 1:
            return self.list_url
        if self.list_url.endswith("index.html"):
            return self.list_url[:-10] + f"index_{page}.html"
        return self.list_url.rstrip("/") + f"/index_{page}.html"

    def matches(self, url: str) -> bool:
        return bool(re.fullmatch(self.detail_url_regex, url))


class _VisibleTextParser(HTMLParser):
    _skip_tags = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.in_h1 = False
        self.h1: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._skip_tags:
            self.skip_depth += 1
        if tag == "h1":
            self.in_h1 = True

    def handle_endtag(self, tag: str) -> None:
        if tag in self._skip_tags and self.skip_depth:
            self.skip_depth -= 1
        if tag == "h1":
            self.in_h1 = False

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        value = re.sub(r"\s+", " ", data).strip()
        if not value:
            return
        self.text.append(value)
        if self.in_h1:
            self.h1.append(value)


def _is_allowed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and port in (None, 443)
        and parsed.username is None
        and parsed.password is None
        and (
        host == "gz.gov.cn" or host.endswith(".gz.gov.cn")
        )
    )


def canonical_url(raw_url: str, base_url: str = "") -> str:
    absolute = urljoin(base_url, unescape(raw_url).replace("\\/", "/").strip())
    parsed = urlparse(absolute)
    path = parsed.path.replace("/mpost_", "/post_")
    return urlunparse(("https", parsed.netloc.lower(), path, "", "", ""))


def _clean_inline(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[*_`]+", "", value)).strip(" |")


def _metadata(raw: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        flexible = r"\s*".join(re.escape(char) for char in label)
        match = re.search(rf"{flexible}\s*[：:]\s*([^\r\n]+)", raw)
        if match:
            return _clean_inline(match.group(1))
    return ""


def _normalize_title(value: str) -> str:
    value = value.lower().replace("（", "(").replace("）", ")")
    return re.sub(r"[\s·•—_《》<>“”\"'，,。；;：:()（）]+", "", value)


def _normalize_document_number(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", value.lower())


def _normalize_body(value: str) -> str:
    value = re.sub(r"^# 来源\s*:.*$", "", value, flags=re.MULTILINE)
    value = re.sub(r"https?://\S+", "", value)
    return re.sub(r"\W+", "", value.lower())


def _body_similarity(left: str, right: str) -> float:
    left = _normalize_body(left)[:30000]
    right = _normalize_body(right)[:30000]
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right, autojunk=True).ratio()


def _extract_entry_metadata(entry: dict[str, Any], output: Path) -> dict[str, Any]:
    enriched = dict(entry)
    path = output / str(entry.get("file") or "")
    raw = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    title_match = TITLE_PATTERN.search(raw)
    enriched["title"] = _clean_inline(
        str(entry.get("title") or (title_match.group(1) if title_match else ""))
    )
    enriched["document_number"] = _clean_inline(
        str(entry.get("document_number") or _metadata(raw, ("文号", "发文字号")))
    )
    enriched["publish_date"] = _clean_inline(
        str(entry.get("publish_date") or _metadata(raw, ("发布日期", "成文日期")))
    )
    enriched["department"] = _clean_inline(
        str(entry.get("department") or _metadata(raw, ("发布机关", "发布部门")))
    )
    enriched["normalized_title"] = _normalize_title(enriched["title"])
    enriched["normalized_document_number"] = _normalize_document_number(
        enriched["document_number"]
    )
    normalized_body = _normalize_body(raw)
    enriched["normalized_content_hash"] = (
        hashlib.sha256(normalized_body.encode("utf-8")).hexdigest()
        if len(normalized_body) >= 200
        else ""
    )
    enriched["_raw"] = raw
    return enriched


def deduplicate_entries(
    entries: list[dict[str, Any]], output: Path
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Classify exact/cross-source aliases while preserving policy versions."""
    enriched = [_extract_entry_metadata(entry, output) for entry in entries]
    parent = list(range(len(enriched)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    by_doc_no_and_title: dict[tuple[str, str], int] = {}
    by_content: dict[str, int] = {}
    by_title: dict[str, list[int]] = {}
    version_pairs: set[tuple[int, int]] = set()

    for index, entry in enumerate(enriched):
        doc_no = entry["normalized_document_number"]
        content_hash = entry["normalized_content_hash"]
        title = entry["normalized_title"]
        # A body can quote the document number of another policy.  Never merge
        # on an extracted number alone; require the normalized title as the
        # second identity component.
        if doc_no and title:
            identity = (doc_no, title)
            if identity in by_doc_no_and_title:
                union(index, by_doc_no_and_title[identity])
            else:
                by_doc_no_and_title[identity] = index
        if content_hash:
            if content_hash in by_content:
                union(index, by_content[content_hash])
            else:
                by_content[content_hash] = index
        if title:
            by_title.setdefault(title, []).append(index)

    ambiguous = 0
    for indexes in by_title.values():
        if len(indexes) < 2:
            continue
        for position, left in enumerate(indexes):
            for right in indexes[position + 1 :]:
                left_doc = enriched[left]["normalized_document_number"]
                right_doc = enriched[right]["normalized_document_number"]
                if left_doc and right_doc and left_doc != right_doc:
                    version_pairs.add(tuple(sorted((left, right))))
                    continue
                same_date = bool(
                    enriched[left]["publish_date"]
                    and enriched[left]["publish_date"] == enriched[right]["publish_date"]
                )
                similarity = _body_similarity(enriched[left]["_raw"], enriched[right]["_raw"])
                if same_date or similarity >= 0.86:
                    union(left, right)
                elif similarity >= 0.72:
                    ambiguous += 1

    groups: dict[int, list[int]] = {}
    for index in range(len(enriched)):
        groups.setdefault(find(index), []).append(index)

    duplicate_count = 0
    source_priority = {
        "gz_gxj": 0,
        "gz_kjj": 0,
        "gz_swj": 0,
        "gz_fgw": 1,
        "hp_department": 2,
        "hp_government": 2,
    }
    for entry in enriched:
        entry["included"] = True
        entry.pop("duplicate_of", None)
        entry.pop("duplicate_reason", None)
        entry.pop("related_version_of", None)

    for indexes in groups.values():
        if len(indexes) < 2:
            continue
        canonical_index = min(
            indexes,
            key=lambda idx: (
                source_priority.get(str(enriched[idx].get("source_key")), 9),
                0 if enriched[idx]["normalized_document_number"] else 1,
                -int(enriched[idx].get("size") or 0),
                str(enriched[idx].get("url") or ""),
            ),
        )
        canonical_url_value = str(enriched[canonical_index].get("url") or "")
        for index in indexes:
            if index == canonical_index:
                continue
            enriched[index]["included"] = False
            enriched[index]["duplicate_of"] = canonical_url_value
            enriched[index]["duplicate_reason"] = "政策文号、标准化正文或同标题正文一致"
            duplicate_count += 1

    for left, right in version_pairs:
        if find(left) == find(right):
            continue
        older, newer = sorted(
            (left, right), key=lambda idx: str(enriched[idx].get("publish_date") or "")
        )
        enriched[newer]["related_version_of"] = str(enriched[older].get("url") or "")

    internal_keys = {
        "normalized_title",
        "normalized_document_number",
        "normalized_content_hash",
        "_raw",
    }
    public_entries = [
        {key: value for key, value in entry.items() if key not in internal_keys}
        for entry in enriched
    ]
    return public_entries, {
        "duplicates": duplicate_count,
        "version_relations": len(version_pairs),
        "ambiguous_duplicates": ambiguous,
        "included": sum(1 for entry in public_entries if entry.get("included", True)),
    }


class PolicyCrawlerEngine:
    def __init__(
        self,
        *,
        config_path: str | Path,
        output_path: str | Path,
        crawl4ai_api: str = "",
        crawl4ai_token: str = "",
        refresh_days: int = 7,
    ) -> None:
        self.config_path = Path(config_path).resolve()
        self.output = Path(output_path).resolve()
        self.crawl4ai_api = crawl4ai_api.rstrip("/")
        self.crawl4ai_token = crawl4ai_token
        self.refresh_days = max(0, refresh_days)

    def load_sources(self) -> list[PolicySource]:
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        if payload.get("version") != 1 or not isinstance(payload.get("sources"), list):
            raise ValueError("政策来源配置格式无效")
        sources: list[PolicySource] = []
        known: set[str] = set()
        for item in payload["sources"]:
            if item.get("enabled", True) is False:
                continue
            source = PolicySource(
                key=str(item["key"]),
                name=str(item["name"]),
                list_url=str(item["list_url"]),
                detail_url_regex=str(item["detail_url_regex"]),
                level=str(item["level"]),
                region=str(item["region"]),
                title_keywords=tuple(str(value) for value in item.get("title_keywords", [])),
            )
            if source.key in known or not re.fullmatch(r"[a-z][a-z0-9_]{1,31}", source.key):
                raise ValueError(f"政策来源标识无效或重复: {source.key}")
            if not _is_allowed_url(source.list_url):
                raise ValueError(f"禁止抓取非广州政府来源: {source.list_url}")
            re.compile(source.detail_url_regex)
            known.add(source.key)
            sources.append(source)
        if not sources:
            raise ValueError("没有启用的政策来源")
        return sources

    def _request_text(self, url: str) -> str:
        if not _is_allowed_url(url):
            raise ValueError(f"禁止抓取非广州政府来源: {url}")
        with httpx.stream(
            "GET",
            url,
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as response:
            response.raise_for_status()
            if not _is_allowed_url(str(response.url)):
                raise ValueError(f"政府来源重定向到非白名单地址: {response.url}")
            content_length = int(response.headers.get("content-length") or 0)
            if content_length > MAX_RESPONSE_BYTES:
                raise ValueError("政策页面超过允许大小")
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    raise ValueError("政策页面超过允许大小")
                chunks.append(chunk)
            encoding = response.encoding or "utf-8"
            return b"".join(chunks).decode(encoding, errors="replace")

    def _discover(self, source: PolicySource, pages: int) -> set[str]:
        links: set[str] = set()
        for page in range(1, pages + 1):
            page_url = source.page_url(page)
            html = self._request_text(page_url)
            for href in HREF_PATTERN.findall(html):
                url = canonical_url(href, page_url)
                if _is_allowed_url(url) and source.matches(url):
                    links.add(url)
        return links

    def _detail_markdown(self, url: str) -> str:
        if self.crawl4ai_api:
            try:
                response = httpx.post(
                    f"{self.crawl4ai_api}/md",
                    json={"url": url, "priority": 10},
                    headers={
                        "Authorization": f"Bearer {self.crawl4ai_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=90,
                )
                response.raise_for_status()
                payload = response.json().get("markdown", "")
                if isinstance(payload, dict):
                    payload = next(
                        (
                            payload.get(key)
                            for key in ("raw_markdown", "markdown_with_citations", "fit_markdown")
                            if isinstance(payload.get(key), str) and payload.get(key).strip()
                        ),
                        "",
                    )
                if isinstance(payload, str) and len(payload.strip()) > 200:
                    return payload.strip()
            except (httpx.HTTPError, ValueError, json.JSONDecodeError):
                pass

        html = self._request_text(url)
        parser = _VisibleTextParser()
        parser.feed(html)
        title = " ".join(parser.h1).strip() or f"广州政策 {url.rsplit('/', 1)[-1]}"
        return f"# {title}\n\n" + "\n\n".join(parser.text)

    def _load_index(self) -> dict[str, dict[str, Any]]:
        index_path = self.output / "_index.json"
        if not index_path.is_file():
            return self._bootstrap_from_versioned_snapshot()
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, list):
            return {}
        valid: dict[str, dict[str, Any]] = {}
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            url = canonical_url(str(entry.get("url") or ""))
            file_path = self.output / str(entry.get("file") or "")
            if _is_allowed_url(url) and file_path.is_file() and file_path.suffix == ".md":
                valid[url] = {**entry, "url": url}
        return valid

    def _bootstrap_from_versioned_snapshot(self) -> dict[str, dict[str, Any]]:
        """Promote the current canonical snapshot into the live incremental index.

        Existing installations use a root directory containing versioned
        ``snapshot-*`` children.  The first admin-triggered refresh must inherit
        every canonical document before it adds recent list-page discoveries.
        """
        try:
            from app.tools.adapters.policy_crawl4ai import PolicyCrawl4AIData

            adapter = PolicyCrawl4AIData(self.output)
            documents = adapter.documents()
        except (OSError, ValueError):
            return {}

        inherited: dict[str, dict[str, Any]] = {}
        for document in documents:
            candidates = [
                adapter.data_dir / document.selected_artifact
                if document.selected_artifact
                else None,
                adapter.data_dir / document.filename,
                adapter.data_dir / "clean" / document.filename,
                adapter.data_dir / "enhanced" / "canonical" / document.filename,
            ]
            source_path = next(
                (candidate.resolve() for candidate in candidates if candidate and candidate.is_file()),
                None,
            )
            if source_path is None:
                continue
            try:
                relative_to_root = source_path.relative_to(self.output)
            except ValueError:
                continue
            url = canonical_url(document.source_url)
            inherited[url] = {
                "url": url,
                "file": relative_to_root.as_posix(),
                "size": source_path.stat().st_size,
                "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                "crawled_at": datetime.fromtimestamp(
                    source_path.stat().st_mtime, timezone.utc
                ).isoformat(),
                "source_key": document.source_key,
                "source_name": document.source_name,
                "level": document.level,
                "region": document.region,
                "title": document.title,
                "document_number": document.document_number,
                "publish_date": document.publish_date,
                "department": document.department,
                "relevant": True,
                "included": True,
                "inherited_from_snapshot": adapter.data_dir.name,
            }
        return inherited

    def _is_fresh(self, entry: dict[str, Any]) -> bool:
        path = self.output / str(entry.get("file") or "")
        if not path.is_file() or path.stat().st_size <= 200:
            return False
        value = entry.get("crawled_at")
        if not value:
            return False
        try:
            crawled_at = datetime.fromisoformat(str(value))
            if crawled_at.tzinfo is None:
                crawled_at = crawled_at.replace(tzinfo=timezone.utc)
        except ValueError:
            return False
        return crawled_at >= datetime.now(timezone.utc) - timedelta(days=self.refresh_days)

    @staticmethod
    def _post_id(url: str) -> str:
        match = re.search(r"post_(\d+)", url)
        return match.group(1) if match else hashlib.sha256(url.encode()).hexdigest()[:12]

    def _save(self, url: str, source: PolicySource, markdown: str) -> dict[str, Any]:
        self.output.mkdir(parents=True, exist_ok=True)
        filename = f"policy_{source.key}_{self._post_id(url)}.md"
        target = self.output / filename
        temporary = self.output / f"{filename}.tmp"
        content = f"# 来源: {url}\n\n{markdown.strip()}\n"
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)
        title_match = TITLE_PATTERN.search(content)
        title = _clean_inline(title_match.group(1) if title_match else "")
        return {
            "url": url,
            "file": filename,
            "size": target.stat().st_size,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "crawled_at": datetime.now(timezone.utc).isoformat(),
            "source_key": source.key,
            "source_name": source.name,
            "level": source.level,
            "region": source.region,
            "title": title,
            "document_number": _metadata(content, ("文号", "发文字号")),
            "publish_date": _metadata(content, ("发布日期", "成文日期")),
            "department": _metadata(content, ("发布机关", "发布部门")),
            "relevant": not source.title_keywords
            or any(keyword in title for keyword in source.title_keywords),
        }

    def refresh(self, *, pages: int, workers: int, force: bool) -> dict[str, Any]:
        if not 1 <= pages <= 20 or not 1 <= workers <= MAX_WORKERS:
            raise ValueError("抓取页数或并发数超出允许范围")
        if self.crawl4ai_api:
            try:
                health = httpx.get(f"{self.crawl4ai_api}/health", timeout=3)
                health.raise_for_status()
            except httpx.HTTPError:
                # Direct official-site extraction is the supported fallback;
                # do not impose a 90-second Crawl4AI timeout per document.
                self.crawl4ai_api = ""
        sources = self.load_sources()
        existing = self._load_index()
        discovered: dict[str, PolicySource] = {}
        source_counts: dict[str, int] = {}
        source_errors: dict[str, str] = {}
        for source in sources:
            try:
                links = self._discover(source, pages)
                source_counts[source.key] = len(links)
                for url in links:
                    discovered[url] = source
            except httpx.HTTPError as exc:
                source_counts[source.key] = 0
                source_errors[source.key] = str(exc)

        if not discovered and not existing:
            raise RuntimeError("没有发现政策链接，且不存在可保留的历史缓存")
        entries = dict(existing)
        pending = [
            (url, source)
            for url, source in discovered.items()
            if force or url not in existing or not self._is_fresh(existing[url])
        ]
        fetched = failed = 0
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._detail_markdown, url): (url, source)
                for url, source in pending
            }
            for future in as_completed(futures):
                url, source = futures[future]
                try:
                    markdown = future.result()
                    if len(markdown.strip()) <= 200:
                        raise ValueError("政策正文过短")
                    entries[url] = self._save(url, source, markdown)
                    fetched += 1
                except Exception:
                    failed += 1

        deduped, dedup_stats = deduplicate_entries(list(entries.values()), self.output)
        deduped.sort(key=lambda item: str(item.get("url") or ""))
        temporary_index = self.output / "_index.json.tmp"
        temporary_index.write_text(
            json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary_index.replace(self.output / "_index.json")
        return {
            "sources": source_counts,
            "source_errors": source_errors,
            "discovered": len(discovered),
            "fetched": fetched,
            "unchanged": max(0, len(discovered) - len(pending)),
            "failed": failed,
            "indexed": len(deduped),
            **dedup_stats,
        }
