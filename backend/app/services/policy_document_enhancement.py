"""Offline policy attachment enhancement through the existing Docling worker."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any
import uuid
import zipfile


DEFAULT_WORKER_PYTHON = Path(r"D:\docling-policy-poc\.venv\Scripts\python.exe")
DEFAULT_WORKER_SCRIPT = Path(r"D:\docling-policy-poc\src\_docling_child.py")
SUPPORTED_STATUSES = {
    "success",
    "partial_success",
    "failed",
    "timeout",
    "unsupported",
    "not_routed",
}


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reasons: tuple[str, ...]
    page_count: int = 0


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_bytes().decode("utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid JSON file: {path}") from exc


def _relative_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _safe_snapshot_path(snapshot: Path, relative: str) -> Path:
    if not relative:
        raise ValueError("Empty snapshot-relative path")
    candidate = (snapshot / relative).resolve()
    try:
        candidate.relative_to(snapshot.resolve())
    except ValueError as exc:
        raise ValueError(f"Path escapes snapshot: {relative}") from exc
    return candidate


def _windows_argument(path: Path) -> str:
    """Return a Windows path when a WSL process launches a Windows worker."""
    value = str(path)
    if os.name == "nt" or re.match(r"^[A-Za-z]:[\\/]", value):
        return value
    if value.startswith("/mnt/") and len(value) > 6:
        drive = value[5].upper()
        tail = value[7:].replace("/", "\\")
        return f"{drive}:\\{tail}"
    return value


def _local_access_path(path: Path) -> Path:
    """Map a Windows absolute path to its WSL mount for local validation."""
    value = str(path)
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", value)
    if os.name != "nt" and match:
        return Path(
            "/mnt",
            match.group(1).lower(),
            match.group(2).replace("\\", "/"),
        )
    return path


def _pdf_route(path: Path) -> RouteDecision:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        page_count = len(reader.pages)
        sample_indices = sorted(
            {
                index
                for index in (
                    0,
                    1,
                    2,
                    page_count // 2,
                    page_count - 2,
                    page_count - 1,
                )
                if 0 <= index < page_count
            }
        )
        sample_text = "\n".join(
            (reader.pages[index].extract_text() or "") for index in sample_indices
        )
    except Exception as exc:
        return RouteDecision("baseline", (f"pdf_feature_error:{type(exc).__name__}",))

    compact = re.sub(r"\s+", "", sample_text)
    if page_count and len(compact) < max(100, len(sample_indices) * 20):
        return RouteDecision("baseline", ("scanned_or_text_unavailable",), page_count)

    reasons: list[str] = []
    if page_count >= 20:
        reasons.append("long_pdf")
    table_terms = ("表格", "单位：", "序号", "申报条件", "支持标准", "咨询方式")
    table_lines = sum(
        1
        for line in sample_text.splitlines()
        if len(re.findall(r"\d+(?:\.\d+)?|[\u4e00-\u9fff]+", line)) >= 6
    )
    if any(term in sample_text for term in table_terms) and table_lines >= 2:
        reasons.append("table_signal")
    wide_columns = sum(1 for line in sample_text.splitlines() if line.count("  ") >= 3)
    if wide_columns >= 3:
        reasons.append("multi_column_signal")

    if page_count < 3 and not reasons:
        return RouteDecision("baseline", ("short_simple_pdf",), page_count)
    if reasons:
        return RouteDecision("docling", tuple(reasons), page_count)
    return RouteDecision("baseline", ("no_complexity_signal",), page_count)


def _docx_route(path: Path) -> RouteDecision:
    try:
        with zipfile.ZipFile(path) as archive:
            document_xml = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        return RouteDecision("baseline", (f"docx_feature_error:{type(exc).__name__}",))

    reasons: list[str] = []
    if b"<w:tbl" in document_xml:
        reasons.append("docx_table")
    if b"<w:cols" in document_xml:
        reasons.append("docx_columns")
    if b"<w:object" in document_xml or b"<w:drawing" in document_xml:
        reasons.append("docx_embedded_object")
    if document_xml.count(b"<w:p") >= 150:
        reasons.append("long_docx")
    if reasons:
        return RouteDecision("docling", tuple(reasons))
    return RouteDecision("baseline", ("simple_docx",))


def route_attachment(path: Path) -> RouteDecision:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf_route(path)
    if suffix == ".docx":
        return _docx_route(path)
    if suffix == ".doc":
        return RouteDecision("docling", ("legacy_doc_requires_conversion",))
    return RouteDecision("baseline", (f"unsupported_format:{suffix or 'none'}",))


class PolicyDocumentEnhancer:
    """Enhance one complete policy snapshot without touching raw/baseline data."""

    def __init__(
        self,
        snapshot: str | Path,
        *,
        worker_python: str | Path = DEFAULT_WORKER_PYTHON,
        worker_script: str | Path = DEFAULT_WORKER_SCRIPT,
        timeout_seconds: int = 600,
        run_id: str | None = None,
        force: bool = False,
    ):
        self.snapshot = Path(snapshot).expanduser().resolve()
        self.worker_python = Path(worker_python)
        self.worker_script = Path(worker_script)
        self.timeout_seconds = timeout_seconds
        self.run_id = run_id or (
            "policy_enhance_"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "_"
            + uuid.uuid4().hex[:8]
        )
        self.force = force
        self.enhanced_root = self.snapshot / "enhanced"

    def run(self) -> dict[str, Any]:
        raw_path = self.snapshot / "_raw_manifest.json"
        clean_path = self.snapshot / "_clean_manifest.json"
        raw_manifest = _read_json(raw_path)
        clean_manifest = _read_json(clean_path)
        if not isinstance(raw_manifest, list) or not isinstance(clean_manifest, list):
            raise ValueError("Raw and clean manifests must contain JSON arrays")
        if not (self.snapshot / "raw").is_dir() or not (self.snapshot / "clean").is_dir():
            raise ValueError(f"Incomplete policy snapshot: {self.snapshot}")

        raw_urls = {
            str(item.get("url", "")).strip()
            for item in raw_manifest
            if isinstance(item, dict)
        }
        results: list[dict[str, Any]] = []
        for entry in clean_manifest:
            if not isinstance(entry, dict):
                continue
            results.extend(self._enhance_entry(entry, raw_urls))

        self.enhanced_root.mkdir(parents=True, exist_ok=True)
        backup = clean_path.with_name(
            f"_clean_manifest.before_{self.run_id}.json"
        )
        if not backup.exists():
            shutil.copy2(clean_path, backup)
        temporary = clean_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(clean_manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(clean_path)

        summary = {
            "run_id": self.run_id,
            "snapshot": str(self.snapshot),
            "concurrency": 1,
            "worker_python": str(self.worker_python),
            "worker_script": str(self.worker_script),
            "results": results,
            "status_counts": self._status_counts(results),
            "selection_counts": self._selection_counts(results),
            "fallback_count": sum(
                bool(result.get("fallback_used")) for result in results
            ),
        }
        report_path = self.enhanced_root / f"_enhancement_run_{self.run_id}.json"
        report_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        summary["report_path"] = str(report_path)
        return summary

    def _enhance_entry(
        self, entry: dict[str, Any], raw_urls: set[str]
    ) -> list[dict[str, Any]]:
        baseline_relative = str(entry.get("clean_file") or "").strip()
        source_url = str(entry.get("url") or "").strip()
        entry.setdefault("baseline_artifact", baseline_relative or None)
        entry.setdefault("selected_artifact", "baseline")
        entry.setdefault("selected_artifact_path", baseline_relative or None)
        entry.setdefault("parser", "baseline")
        entry.setdefault("parse_status", "not_routed")
        entry.setdefault("fallback_used", False)
        entry.setdefault("parse_error", None)

        attachments = entry.get("attachments")
        if not isinstance(attachments, list):
            attachments = []
        previous = {
            str(item.get("input_file", "")): item
            for item in entry.get("document_enhancements", [])
            if isinstance(item, dict)
        }
        document_results: list[dict[str, Any]] = []
        canonical_text: str | None = None
        baseline_path: Path | None = None
        if baseline_relative:
            try:
                baseline_path = _safe_snapshot_path(self.snapshot, baseline_relative)
                if baseline_path.is_file():
                    canonical_text = baseline_path.read_text(
                        encoding="utf-8", errors="replace"
                    )
            except ValueError:
                baseline_path = None

        selected_docling: list[dict[str, Any]] = []
        for attachment in attachments:
            if not isinstance(attachment, dict) or attachment.get("downloaded") is not True:
                continue
            relative = str(attachment.get("file") or "").strip()
            if not relative:
                continue
            if entry.get("included") is False:
                document_results.append(
                    {
                        "policy_id": self._policy_id(entry),
                        "source_url": source_url,
                        "input_file": relative,
                        "input_sha256": str(attachment.get("sha256") or "").lower(),
                        "baseline_artifact": baseline_relative or None,
                        "enhanced_artifact": None,
                        "selected_artifact": "baseline",
                        "parser": "baseline",
                        "parser_version": None,
                        "run_id": self.run_id,
                        "parse_status": "not_routed",
                        "page_count": 0,
                        "success_pages": 0,
                        "failed_pages": [],
                        "fallback_used": False,
                        "parse_error": None,
                        "route": "baseline",
                        "route_reasons": ["record_excluded"],
                        "validation_errors": [],
                    }
                )
                continue
            existing = previous.get(relative)
            if (
                not self.force
                and existing
                and self._existing_enhancement_is_reusable(existing)
            ):
                enhanced_path = _safe_snapshot_path(
                    self.snapshot, existing["enhanced_artifact"]
                )
                merged = (
                    self._replace_attachment_section(
                        canonical_text,
                        str(attachment.get("label") or Path(relative).name),
                        enhanced_path.read_text(encoding="utf-8", errors="replace"),
                    )
                    if canonical_text is not None
                    else None
                )
                if merged is not None:
                    canonical_text = merged
                    reused = dict(existing)
                    reused["reused"] = True
                    reused["last_checked_run_id"] = self.run_id
                    document_results.append(reused)
                    selected_docling.append(reused)
                    continue

            result = self._process_attachment(
                entry=entry,
                attachment=attachment,
                source_identity_valid=bool(source_url and source_url in raw_urls),
            )
            document_results.append(result)
            if result["selected_artifact"] == "docling":
                if canonical_text is None:
                    result = self._fallback(
                        result, "baseline artifact unavailable for canonical merge"
                    )
                    document_results[-1] = result
                else:
                    enhanced_path = _safe_snapshot_path(
                        self.snapshot, result["enhanced_artifact"]
                    )
                    merged = self._replace_attachment_section(
                        canonical_text,
                        str(attachment.get("label") or Path(relative).name),
                        enhanced_path.read_text(encoding="utf-8", errors="replace"),
                    )
                    if merged is None:
                        result = self._fallback(
                            result,
                            "attachment section not found in baseline canonical artifact",
                        )
                        document_results[-1] = result
                    else:
                        canonical_text = merged
                        selected_docling.append(result)

        entry["document_enhancements"] = document_results
        if selected_docling and canonical_text is not None:
            policy_id = self._policy_id(entry)
            canonical_path = self.enhanced_root / "canonical" / f"{policy_id}.md"
            canonical_path.parent.mkdir(parents=True, exist_ok=True)
            canonical_path.write_text(canonical_text, encoding="utf-8")
            selected_path = _relative_posix(canonical_path, self.snapshot)
            latest = selected_docling[-1]
            entry.update(
                {
                    "enhanced_artifact": latest.get("enhanced_artifact"),
                    "selected_artifact": "docling",
                    "selected_artifact_path": selected_path,
                    "parser": "docling",
                    "parser_version": latest.get("parser_version"),
                    "run_id": self.run_id,
                    "parse_status": "success",
                    "input_sha256": latest.get("input_sha256"),
                    "page_count": sum(
                        int(item.get("page_count") or 0)
                        for item in selected_docling
                    ),
                    "success_pages": sum(
                        int(item.get("success_pages") or 0)
                        for item in selected_docling
                    ),
                    "failed_pages": [],
                    "fallback_used": any(
                        item.get("fallback_used") for item in document_results
                    ),
                    "parse_error": None,
                }
            )
        elif document_results:
            statuses = [str(item.get("parse_status")) for item in document_results]
            attempted = any(status != "not_routed" for status in statuses)
            latest = document_results[-1]
            entry.update(
                {
                    "enhanced_artifact": latest.get("enhanced_artifact"),
                    "selected_artifact": "baseline",
                    "selected_artifact_path": baseline_relative or None,
                    "parser": "baseline",
                    "parser_version": latest.get("parser_version"),
                    "run_id": self.run_id,
                    "parse_status": statuses[-1],
                    "input_sha256": latest.get("input_sha256"),
                    "page_count": int(latest.get("page_count") or 0),
                    "success_pages": int(latest.get("success_pages") or 0),
                    "failed_pages": list(latest.get("failed_pages") or []),
                    "fallback_used": attempted,
                    "parse_error": next(
                        (
                            item.get("parse_error")
                            for item in reversed(document_results)
                            if item.get("parse_error")
                        ),
                        None,
                    ),
                }
            )
            if baseline_path is None or not baseline_path.is_file():
                entry["included"] = False
                entry["parse_error"] = (
                    entry.get("parse_error")
                    or "baseline artifact is unavailable"
                )
        return document_results

    def _process_attachment(
        self,
        *,
        entry: dict[str, Any],
        attachment: dict[str, Any],
        source_identity_valid: bool,
    ) -> dict[str, Any]:
        relative = str(attachment.get("file") or "").strip()
        base = {
            "policy_id": self._policy_id(entry),
            "source_url": str(entry.get("url") or ""),
            "input_file": relative,
            "input_sha256": str(attachment.get("sha256") or "").lower(),
            "baseline_artifact": str(entry.get("clean_file") or "") or None,
            "enhanced_artifact": None,
            "selected_artifact": "baseline",
            "parser": "baseline",
            "parser_version": None,
            "run_id": self.run_id,
            "parse_status": "failed",
            "page_count": 0,
            "success_pages": 0,
            "failed_pages": [],
            "fallback_used": True,
            "parse_error": None,
            "route": "baseline",
            "route_reasons": [],
            "validation_errors": [],
        }
        if not source_identity_valid:
            return self._fallback(base, "clean record has no matching raw source URL")
        try:
            input_path = _safe_snapshot_path(self.snapshot, relative)
        except ValueError as exc:
            return self._fallback(base, str(exc))
        if not input_path.is_file():
            return self._fallback(base, "attachment file is missing")

        actual_sha = _sha256_file(input_path)
        if not base["input_sha256"] or actual_sha != base["input_sha256"]:
            return self._fallback(base, "attachment SHA-256 does not match manifest")

        decision = route_attachment(input_path)
        base.update(
            {
                "route": decision.route,
                "route_reasons": list(decision.reasons),
                "page_count": decision.page_count,
            }
        )
        if decision.route != "docling":
            base.update(
                {
                    "parse_status": "not_routed",
                    "fallback_used": False,
                    "parse_error": None,
                }
            )
            return base

        worker_input = input_path
        if input_path.suffix.lower() == ".doc":
            converted = self.enhanced_root / "converted" / (
                self._document_id(entry, attachment) + ".docx"
            )
            conversion_error = self._convert_legacy_doc(input_path, converted)
            if conversion_error:
                base["parse_status"] = "unsupported"
                return self._fallback(base, conversion_error)
            worker_input = converted
            base["converted_artifact"] = _relative_posix(converted, self.snapshot)
            base["converted_sha256"] = _sha256_file(converted)

        doc_id = self._document_id(entry, attachment)
        try:
            completed = self._invoke_worker(worker_input, doc_id)
        except subprocess.TimeoutExpired:
            base["parse_status"] = "timeout"
            return self._fallback(base, f"worker timeout after {self.timeout_seconds}s")
        except (OSError, ValueError) as exc:
            return self._fallback(base, f"worker unavailable: {exc}")
        if completed.returncode != 0:
            base.update(
                {
                    "worker_stdout": completed.stdout[-2000:],
                    "worker_stderr": completed.stderr[-2000:],
                }
            )
            detail = (completed.stderr or completed.stdout).strip()[-500:]
            return self._fallback(
                base,
                f"worker exited with code {completed.returncode}"
                + (f": {detail}" if detail else ""),
            )

        markdown_path = self.enhanced_root / "docling" / f"{doc_id}.md"
        metrics_path = self.enhanced_root / "docling" / f"{doc_id}.metrics.json"
        try:
            metrics = _read_json(metrics_path)
        except ValueError as exc:
            return self._fallback(base, str(exc))
        validation_errors = self._validate_worker_result(
            entry=entry,
            attachment=attachment,
            worker_input=worker_input,
            markdown_path=markdown_path,
            metrics_path=metrics_path,
            metrics=metrics,
        )
        status = self._normalize_status(metrics.get("status"))
        base.update(
            {
                "enhanced_artifact": (
                    _relative_posix(markdown_path, self.snapshot)
                    if markdown_path.is_file()
                    else None
                ),
                "parser_version": metrics.get("model_version"),
                "parse_status": status,
                "page_count": int(metrics.get("pages") or 0),
                "success_pages": int(metrics.get("success_pages") or 0),
                "failed_pages": list(metrics.get("failed_pages") or []),
                "validation_errors": validation_errors,
                "metrics_artifact": _relative_posix(metrics_path, self.snapshot),
                "worker_stdout": completed.stdout[-1000:],
                "worker_stderr": completed.stderr[-1000:],
            }
        )
        if status != "success":
            return self._fallback(base, f"worker status is {status}")
        if validation_errors:
            return self._fallback(
                base, "validation failed: " + "; ".join(validation_errors)
            )
        base.update(
            {
                "selected_artifact": "docling",
                "parser": "docling",
                "fallback_used": False,
                "parse_error": None,
            }
        )
        return base

    def _invoke_worker(
        self, worker_input: Path, doc_id: str
    ) -> subprocess.CompletedProcess[str]:
        if (
            not _local_access_path(self.worker_python).is_file()
            or not _local_access_path(self.worker_script).is_file()
        ):
            raise OSError("Docling worker executable or script does not exist")
        self.enhanced_root.mkdir(parents=True, exist_ok=True)
        (
            self.enhanced_root / "docling" / "segments" / doc_id
        ).mkdir(parents=True, exist_ok=True)
        worker_executable = (
            str(self.worker_python)
            if os.name == "nt"
            else str(_local_access_path(self.worker_python))
        )
        command = [
            worker_executable,
            _windows_argument(self.worker_script),
            "--input",
            _windows_argument(worker_input),
            "--out",
            _windows_argument(self.enhanced_root),
            "--run-id",
            self.run_id,
            "--doc-id",
            doc_id,
            "--seg-threshold",
            "20",
            "--seg-size",
            "15",
        ]
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.timeout_seconds,
            check=False,
        )

    def _convert_legacy_doc(self, source: Path, target: Path) -> str | None:
        target.parent.mkdir(parents=True, exist_ok=True)
        script = r"""
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
  $source = [Environment]::GetEnvironmentVariable("POLICY_DOC_SOURCE")
  $target = [Environment]::GetEnvironmentVariable("POLICY_DOC_TARGET")
  $document = $word.Documents.Open($source, $true)
  $document.SaveAs2($target, 16)
  $document.Close()
  Write-Output "OK"
} catch {
  Write-Error $_
  exit 1
} finally {
  try { $word.Quit() } catch {}
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
  [System.GC]::Collect()
}
"""
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        environment = os.environ.copy()
        environment["POLICY_DOC_SOURCE"] = _windows_argument(source)
        environment["POLICY_DOC_TARGET"] = _windows_argument(target)
        if os.name != "nt":
            wslenv_entries = [
                entry
                for entry in environment.get("WSLENV", "").split(":")
                if entry
            ]
            exported_names = {
                entry.split("/", 1)[0] for entry in wslenv_entries
            }
            for name in ("POLICY_DOC_SOURCE", "POLICY_DOC_TARGET"):
                if name not in exported_names:
                    wslenv_entries.append(name)
            environment["WSLENV"] = ":".join(wslenv_entries)
        try:
            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-EncodedCommand",
                    encoded,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=90,
                check=False,
                env=environment,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"Word COM conversion unavailable: {exc}"
        if completed.returncode != 0 or not target.is_file():
            return "Word COM conversion failed"
        return None

    def _validate_worker_result(
        self,
        *,
        entry: dict[str, Any],
        attachment: dict[str, Any],
        worker_input: Path,
        markdown_path: Path,
        metrics_path: Path,
        metrics: dict[str, Any],
    ) -> list[str]:
        errors: list[str] = []
        for path in (markdown_path, metrics_path):
            try:
                path.resolve().relative_to(self.enhanced_root.resolve())
            except ValueError:
                errors.append(f"output path escapes enhanced root: {path}")
        if metrics.get("input_sha256") != _sha256_file(worker_input):
            errors.append("worker input SHA-256 mismatch")
        if metrics.get("run_id") != self.run_id:
            errors.append("worker run_id mismatch")
        if not markdown_path.is_file():
            errors.append("worker markdown is missing")
            markdown = ""
        else:
            markdown = markdown_path.read_text(encoding="utf-8", errors="replace").strip()
            if not markdown:
                errors.append("worker markdown is empty")
            else:
                errors.extend(self._markdown_quality_errors(markdown))
        page_count = int(metrics.get("pages") or 0)
        success_pages = int(metrics.get("success_pages") or 0)
        failed_pages = list(metrics.get("failed_pages") or [])
        if worker_input.suffix.lower() == ".pdf":
            if page_count <= 0:
                errors.append("worker reported no pages")
            if success_pages != page_count or failed_pages:
                errors.append("worker page coverage is incomplete")
        elif failed_pages:
            errors.append("worker reported failed document pages")
        if not metrics.get("model_version"):
            errors.append("worker model version is missing")
        label = str(attachment.get("label") or "").strip()
        title = str(entry.get("title") or "").strip()
        identity_terms = [
            re.sub(r"\W+", "", value)
            for value in (label, title)
            if len(re.sub(r"\W+", "", value)) >= 6
        ]
        if identity_terms and not any(
            term[: min(12, len(term))] in re.sub(r"\W+", "", markdown)
            for term in identity_terms
        ):
            errors.append("policy/attachment identity is not present in output")
        return errors

    @staticmethod
    def _replace_attachment_section(
        baseline: str, label: str, enhanced_markdown: str
    ) -> str | None:
        label = label.strip()
        headings = list(
            re.finditer(r"(?m)^##\s+附件正文[：:]\s*(.+?)\s*$", baseline)
        )
        normalized_label = re.sub(r"\s+", "", label)
        for index, match in enumerate(headings):
            heading_label = re.sub(r"\s+", "", match.group(1))
            if heading_label != normalized_label:
                continue
            end = headings[index + 1].start() if index + 1 < len(headings) else len(baseline)
            replacement = (
                baseline[: match.end()].rstrip()
                + "\n\n"
                + enhanced_markdown.strip()
                + "\n"
            )
            return replacement + baseline[end:].lstrip("\n")
        return None

    def _relative_file_exists(self, relative: Any) -> bool:
        try:
            return _safe_snapshot_path(self.snapshot, str(relative)).is_file()
        except ValueError:
            return False

    def _existing_enhancement_is_reusable(
        self, existing: dict[str, Any]
    ) -> bool:
        if (
            existing.get("parse_status") != "success"
            or existing.get("selected_artifact") != "docling"
            or not self._relative_file_exists(existing.get("enhanced_artifact"))
        ):
            return False
        try:
            path = _safe_snapshot_path(
                self.snapshot, str(existing["enhanced_artifact"])
            )
            markdown = path.read_text(encoding="utf-8", errors="replace").strip()
        except (OSError, ValueError):
            return False
        return bool(markdown) and not self._markdown_quality_errors(markdown)

    @staticmethod
    def _markdown_quality_errors(markdown: str) -> list[str]:
        image_placeholders = re.findall(
            r"<!--\s*image\s*-->", markdown, flags=re.IGNORECASE
        )
        visible = re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)
        visible_compact = re.sub(r"\s+", "", visible)
        if image_placeholders and len(visible_compact) < 100:
            return ["worker output is image-only while OCR is disabled"]
        return []

    @staticmethod
    def _normalize_status(status: Any) -> str:
        value = str(status or "failed")
        if value == "error" or value == "failure":
            return "failed"
        return value if value in SUPPORTED_STATUSES else "failed"

    @staticmethod
    def _fallback(result: dict[str, Any], error: str) -> dict[str, Any]:
        updated = dict(result)
        updated.update(
            {
                "selected_artifact": "baseline",
                "parser": "baseline",
                "fallback_used": updated.get("parse_status") != "not_routed",
                "parse_error": error,
            }
        )
        return updated

    @staticmethod
    def _policy_id(entry: dict[str, Any]) -> str:
        source = "|".join(
            (
                str(entry.get("source_key") or ""),
                str(entry.get("url") or ""),
                str(entry.get("file") or ""),
            )
        )
        return "policy_" + hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def _document_id(
        cls, entry: dict[str, Any], attachment: dict[str, Any]
    ) -> str:
        source = "|".join(
            (
                cls._policy_id(entry),
                str(attachment.get("file") or ""),
                str(attachment.get("sha256") or ""),
            )
        )
        return "doc_" + hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _status_counts(results: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for result in results:
            status = str(result.get("parse_status") or "failed")
            counts[status] = counts.get(status, 0) + 1
        return counts

    @staticmethod
    def _selection_counts(results: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for result in results:
            selection = str(result.get("selected_artifact") or "baseline")
            counts[selection] = counts.get(selection, 0) + 1
        return counts
