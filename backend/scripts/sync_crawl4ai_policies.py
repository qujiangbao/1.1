#!/usr/bin/env python3
"""Validate and sync output from crawl4ai-tools into the backend policy cache."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from urllib.parse import urlparse

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.tools.adapters.policy_crawl4ai import PolicyCrawl4AIData  # noqa: E402

ALLOWED_LEVELS = {"", "municipal", "district"}


def is_allowed_source_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        host == "gz.gov.cn" or host.endswith(".gz.gov.cn")
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("/tmp/gz_gov_policies"),
        help="Directory produced by gz_gov_crawler.py",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=BACKEND_ROOT / "data" / "policies_gz_gov",
        help="Backend cache directory",
    )
    return parser.parse_args()


def validated_entries(source: Path) -> list[dict]:
    index_path = source / "_index.json"
    try:
        entries = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read valid crawler index: {index_path}") from exc
    if not isinstance(entries, list) or not entries:
        raise ValueError("Crawler index must be a non-empty JSON array")

    valid: list[dict] = []
    source_root = source.resolve()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Every crawler index entry must be an object")
        url = str(entry.get("url", ""))
        filename = str(entry.get("file", ""))
        if not is_allowed_source_url(url):
            raise ValueError(f"Unsupported policy source URL: {url}")
        level = str(entry.get("level", ""))
        region = str(entry.get("region", ""))
        if level not in ALLOWED_LEVELS:
            raise ValueError(f"Unsupported policy level: {level}")
        if region and not region.startswith("广州市"):
            raise ValueError(f"Unsupported policy region: {region}")
        candidate = (source_root / filename).resolve()
        try:
            candidate.relative_to(source_root)
        except ValueError as exc:
            raise ValueError(f"Policy file escapes source directory: {filename}") from exc
        if not candidate.is_file() or candidate.suffix.lower() != ".md":
            raise ValueError(f"Policy Markdown missing: {candidate}")
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        validated = {
            "url": url,
            "file": candidate.name,
            "size": candidate.stat().st_size,
            "sha256": digest,
        }
        for key in (
            "crawled_at",
            "source_key",
            "source_name",
            "level",
            "region",
            "relevant",
        ):
            value = entry.get(key)
            if value not in (None, ""):
                validated[key] = value
        valid.append(validated)
    return valid


def sync(source: Path, target: Path) -> dict[str, int]:
    source = source.resolve()
    target = target.resolve()
    entries = validated_entries(source)
    target.mkdir(parents=True, exist_ok=True)

    copied = 0
    unchanged = 0
    for entry in entries:
        source_file = source / entry["file"]
        target_file = target / entry["file"]
        if (
            target_file.is_file()
            and hashlib.sha256(target_file.read_bytes()).hexdigest()
            == entry["sha256"]
        ):
            unchanged += 1
            continue
        temporary_file = target / f"{entry['file']}.tmp"
        shutil.copy2(source_file, temporary_file)
        temporary_file.replace(target_file)
        copied += 1

    # Publish the index last so readers never observe an index whose documents
    # have not been copied yet.
    temporary_index = target / "_index.json.tmp"
    temporary_index.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_index.replace(target / "_index.json")

    catalog_payload = PolicyCrawl4AIData(target).catalog_payload()
    temporary_catalog = target / "_catalog.json.tmp"
    temporary_catalog.write_text(
        json.dumps(catalog_payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary_catalog.replace(target / "_catalog.json")
    return {
        "total": len(entries),
        "copied": copied,
        "unchanged": unchanged,
    }


def main() -> int:
    args = parse_args()
    try:
        report = sync(args.source, args.target)
    except ValueError as exc:
        print(f"Policy sync failed: {exc}", file=sys.stderr)
        return 1
    print(
        "Synced "
        f"{report['total']} government policies "
        f"({report['copied']} copied, {report['unchanged']} unchanged) "
        f"to {args.target.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
