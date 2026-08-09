from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from app.services.policy_document_enhancement import (
    PolicyDocumentEnhancer,
    route_attachment,
)
from app.tools.adapters.policy_crawl4ai import PolicyCrawl4AIData


SOURCE_URL = "https://www.gz.gov.cn/example/content/post_123.html"
TITLE = "广州市机器人扶持政策"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_docx(path: Path, *, complex_document: bool = True) -> None:
    body = "<w:tbl><w:tr><w:tc/></w:tr></w:tbl>" if complex_document else "<w:p/>"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>'
            ),
        )


def _write_snapshot(
    tmp_path: Path,
    *,
    attachment_count: int = 1,
    bad_hash: bool = False,
) -> Path:
    snapshot = tmp_path / "snapshot-20260728-000000"
    (snapshot / "raw").mkdir(parents=True)
    (snapshot / "clean").mkdir()
    attachment_dir = snapshot / "attachments" / "policy"
    attachment_dir.mkdir(parents=True)
    raw_file = snapshot / "raw" / "policy.md"
    raw_file.write_text(f"# {TITLE}\n", encoding="utf-8")

    attachments = []
    sections = [f"# {TITLE}\n"]
    for index in range(attachment_count):
        label = f"complex-{index + 1}.docx"
        attachment = attachment_dir / label
        _write_docx(attachment)
        relative = attachment.relative_to(snapshot).as_posix()
        attachments.append(
            {
                "label": label,
                "url": f"https://www.gz.gov.cn/attachment/{label}",
                "file": relative,
                "downloaded": True,
                "sha256": "0" * 64 if bad_hash else _sha256(attachment),
            }
        )
        sections.append(f"## 附件正文：{label}\n\nbaseline attachment {index + 1}\n")

    clean_file = snapshot / "clean" / "policy.md"
    clean_file.write_text("\n".join(sections), encoding="utf-8")
    raw_entry = {
        "source_key": "gz_test",
        "url": SOURCE_URL,
        "file": "raw/policy.md",
        "sha256": _sha256(raw_file),
    }
    clean_entry = {
        **raw_entry,
        "title": TITLE,
        "included": True,
        "clean_file": "clean/policy.md",
        "clean_sha256": _sha256(clean_file),
        "attachments": attachments,
    }
    (snapshot / "_raw_manifest.json").write_text(
        json.dumps([raw_entry], ensure_ascii=False),
        encoding="utf-8",
    )
    (snapshot / "_clean_manifest.json").write_text(
        json.dumps([clean_entry], ensure_ascii=False),
        encoding="utf-8",
    )
    (snapshot / "_run_report.json").write_text("{}", encoding="utf-8")
    (snapshot / "_clean_report.json").write_text(
        json.dumps({"raw_records": 1, "included_records": 1, "failed_records": 0}),
        encoding="utf-8",
    )
    return snapshot


class FakeEnhancer(PolicyDocumentEnhancer):
    def __init__(
        self,
        *args,
        statuses: list[str] | None = None,
        metrics_hash_mismatch: bool = False,
        timeout: bool = False,
        page_count: int = 0,
        markdown_text: str | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.statuses = statuses or ["success"]
        self.metrics_hash_mismatch = metrics_hash_mismatch
        self.raise_timeout = timeout
        self.page_count = page_count
        self.markdown_text = markdown_text
        self.calls = 0

    def _invoke_worker(self, worker_input: Path, doc_id: str):
        if self.raise_timeout:
            raise subprocess.TimeoutExpired(["fake-worker"], self.timeout_seconds)
        status = self.statuses[min(self.calls, len(self.statuses) - 1)]
        self.calls += 1
        output_dir = self.enhanced_root / "docling"
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown = output_dir / f"{doc_id}.md"
        metrics = output_dir / f"{doc_id}.metrics.json"
        markdown.write_text(
            self.markdown_text
            or f"# {TITLE}\n\nDocling enhanced content for {worker_input.name}.",
            encoding="utf-8",
        )
        failed_pages = [2] if status == "partial_success" else []
        success_pages = (
            max(0, self.page_count - 1)
            if status == "partial_success"
            else self.page_count
        )
        metrics.write_text(
            json.dumps(
                {
                    "engine": "docling",
                    "run_id": self.run_id,
                    "model_version": (
                        "docling==2.115.0; layout=heron; table=TableFormerV1; ocr=false"
                    ),
                    "input_sha256": (
                        "f" * 64
                        if self.metrics_hash_mismatch
                        else _sha256(worker_input)
                    ),
                    "pages": self.page_count,
                    "success_pages": success_pages,
                    "failed_pages": failed_pages,
                    "status": status,
                    "markdown_chars": markdown.stat().st_size,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            args=["fake-worker"],
            returncode=0,
            stdout="ok",
            stderr="",
        )


def _manifest(snapshot: Path) -> dict:
    return json.loads(
        (snapshot / "_clean_manifest.json").read_text(encoding="utf-8")
    )[0]


def test_route_attachment_uses_deterministic_docx_and_legacy_rules(tmp_path):
    complex_docx = tmp_path / "complex.docx"
    simple_docx = tmp_path / "simple.docx"
    legacy_doc = tmp_path / "legacy.doc"
    _write_docx(complex_docx, complex_document=True)
    _write_docx(simple_docx, complex_document=False)
    legacy_doc.write_bytes(b"legacy")

    assert route_attachment(complex_docx).route == "docling"
    assert route_attachment(simple_docx).route == "baseline"
    assert route_attachment(legacy_doc).route == "docling"


def test_legacy_doc_conversion_exports_paths_through_wslenv(
    tmp_path, monkeypatch
):
    source = tmp_path / "legacy.doc"
    target = tmp_path / "converted.docx"
    source.write_bytes(b"legacy")
    captured = {}

    def fake_run(*_args, **kwargs):
        captured.update(kwargs["env"])
        target.write_bytes(b"converted")
        return subprocess.CompletedProcess(
            args=["powershell.exe"],
            returncode=0,
            stdout="OK",
            stderr="",
        )

    monkeypatch.setattr(
        "app.services.policy_document_enhancement.os.name", "posix"
    )
    monkeypatch.setattr(
        "app.services.policy_document_enhancement.subprocess.run", fake_run
    )

    error = PolicyDocumentEnhancer(tmp_path)._convert_legacy_doc(
        source, target
    )

    assert error is None
    wslenv = captured["WSLENV"].split(":")
    assert "POLICY_DOC_SOURCE" in wslenv
    assert "POLICY_DOC_TARGET" in wslenv
    assert captured["POLICY_DOC_SOURCE"].endswith("legacy.doc")
    assert captured["POLICY_DOC_TARGET"].endswith("converted.docx")


def test_long_pdf_samples_middle_and_tail_before_scan_fallback(
    tmp_path, monkeypatch
):
    import pypdf

    class FakePage:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    class FakeReader:
        def __init__(self, _path):
            self.pages = [FakePage("") for _ in range(93)]
            self.pages[46] = FakePage(
                "序号 申报条件 支持标准 单位 金额 咨询方式\n" * 10
            )
            self.pages[91] = FakePage("政策正文" * 100)

    monkeypatch.setattr(pypdf, "PdfReader", FakeReader)
    path = tmp_path / "long.pdf"
    path.write_bytes(b"%PDF-fake")

    decision = route_attachment(path)

    assert decision.route == "docling"
    assert decision.page_count == 93
    assert "long_pdf" in decision.reasons


def test_success_selects_canonical_and_local_catalog_preserves_provenance(tmp_path):
    snapshot = _write_snapshot(tmp_path)
    enhancer = FakeEnhancer(snapshot, run_id="run-success")

    summary = enhancer.run()
    entry = _manifest(snapshot)
    canonical = snapshot / entry["selected_artifact_path"]

    assert summary["status_counts"] == {"success": 1}
    assert summary["selection_counts"] == {"docling": 1}
    assert summary["fallback_count"] == 0
    assert entry["selected_artifact"] == "docling"
    assert entry["parser"] == "docling"
    assert entry["parse_status"] == "success"
    assert entry["fallback_used"] is False
    assert canonical.is_file()
    assert "Docling enhanced content" in canonical.read_text(encoding="utf-8")
    assert "baseline attachment 1" not in canonical.read_text(encoding="utf-8")
    assert (
        snapshot / "_clean_manifest.before_run-success.json"
    ).is_file()

    result = PolicyCrawl4AIData(snapshot).search("机器人", top_k=1)[0]
    assert result["metadata"]["parser"] == "docling"
    assert result["metadata"]["parse_status"] == "success"
    assert result["metadata"]["selected_artifact"] == entry["selected_artifact_path"]
    assert result["metadata"]["source_url"] == SOURCE_URL


def test_partial_result_falls_back_to_baseline(tmp_path):
    snapshot = _write_snapshot(tmp_path)
    summary = FakeEnhancer(
        snapshot,
        run_id="run-partial",
        statuses=["partial_success"],
        page_count=2,
    ).run()
    entry = _manifest(snapshot)

    assert summary["status_counts"] == {"partial_success": 1}
    assert entry["selected_artifact"] == "baseline"
    assert entry["selected_artifact_path"] == "clean/policy.md"
    assert entry["parse_status"] == "partial_success"
    assert entry["fallback_used"] is True
    assert entry["page_count"] == 2
    assert entry["success_pages"] == 1
    assert entry["failed_pages"] == [2]
    assert "TableFormerV1" in entry["parser_version"]


def test_timeout_falls_back_without_aborting_batch(tmp_path):
    snapshot = _write_snapshot(tmp_path)
    summary = FakeEnhancer(
        snapshot,
        run_id="run-timeout",
        timeout=True,
        timeout_seconds=1,
    ).run()

    assert summary["status_counts"] == {"timeout": 1}
    assert _manifest(snapshot)["selected_artifact"] == "baseline"


def test_missing_worker_falls_back_to_baseline(tmp_path):
    snapshot = _write_snapshot(tmp_path)
    summary = PolicyDocumentEnhancer(
        snapshot,
        worker_python=tmp_path / "missing-python",
        worker_script=tmp_path / "missing-worker.py",
        run_id="run-missing",
    ).run()

    assert summary["status_counts"] == {"failed": 1}
    assert "worker unavailable" in _manifest(snapshot)["parse_error"]


def test_worker_invocation_prepares_segment_metrics_directory_and_keeps_ocr_off(
    tmp_path, monkeypatch
):
    snapshot = _write_snapshot(tmp_path)
    worker_python = tmp_path / "python.exe"
    worker_script = tmp_path / "worker.py"
    worker_input = tmp_path / "input.pdf"
    for path in (worker_python, worker_script, worker_input):
        path.write_bytes(b"x")
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    enhancer = PolicyDocumentEnhancer(
        snapshot,
        worker_python=worker_python,
        worker_script=worker_script,
        run_id="run-command",
    )

    enhancer._invoke_worker(worker_input, "doc-test")

    assert (
        enhancer.enhanced_root / "docling" / "segments" / "doc-test"
    ).is_dir()
    assert "--ocr" not in captured["command"]
    assert captured["command"][-4:] == [
        "--seg-threshold",
        "20",
        "--seg-size",
        "15",
    ]
    assert captured["kwargs"]["timeout"] == 600


def test_manifest_hash_mismatch_rejects_attachment_before_worker(tmp_path):
    snapshot = _write_snapshot(tmp_path, bad_hash=True)
    enhancer = FakeEnhancer(snapshot, run_id="run-bad-input")

    summary = enhancer.run()

    assert enhancer.calls == 0
    assert summary["status_counts"] == {"failed": 1}
    assert "SHA-256" in _manifest(snapshot)["parse_error"]


def test_worker_metrics_hash_mismatch_rejects_docling_output(tmp_path):
    snapshot = _write_snapshot(tmp_path)
    FakeEnhancer(
        snapshot,
        run_id="run-bad-metrics",
        metrics_hash_mismatch=True,
    ).run()

    entry = _manifest(snapshot)
    assert entry["selected_artifact"] == "baseline"
    assert "worker input SHA-256 mismatch" in entry["parse_error"]


def test_image_only_output_falls_back_when_ocr_is_disabled(tmp_path):
    snapshot = _write_snapshot(tmp_path)
    summary = FakeEnhancer(
        snapshot,
        run_id="run-image-only",
        markdown_text="附件1：政策办理流程图\n\n<!-- image -->",
    ).run()

    entry = _manifest(snapshot)
    assert summary["selection_counts"] == {"baseline": 1}
    assert summary["fallback_count"] == 1
    assert entry["selected_artifact"] == "baseline"
    assert "image-only while OCR is disabled" in entry["parse_error"]


def test_image_only_existing_artifact_is_not_reused(tmp_path):
    snapshot = _write_snapshot(tmp_path)
    enhancer = FakeEnhancer(snapshot, run_id="run-revalidate")

    enhancer.run()
    entry = _manifest(snapshot)
    enhanced = snapshot / entry["enhanced_artifact"]
    enhanced.write_text(
        "附件1：政策办理流程图\n\n<!-- image -->",
        encoding="utf-8",
    )

    summary = enhancer.run()

    assert enhancer.calls == 2
    assert summary["selection_counts"] == {"docling": 1}
    assert "reused" not in summary["results"][0]


def test_repeated_run_is_idempotent_and_does_not_duplicate_records(tmp_path):
    snapshot = _write_snapshot(tmp_path)
    enhancer = FakeEnhancer(snapshot, run_id="run-idempotent")

    enhancer.run()
    first_manifest = _manifest(snapshot)
    second_summary = enhancer.run()
    second_manifest = _manifest(snapshot)

    assert enhancer.calls == 1
    assert len(second_manifest["document_enhancements"]) == 1
    assert second_manifest["selected_artifact_path"] == first_manifest[
        "selected_artifact_path"
    ]
    assert second_summary["results"][0]["reused"] is True
    assert second_summary["results"][0]["last_checked_run_id"] == "run-idempotent"


def test_one_attachment_failure_does_not_block_later_success(tmp_path):
    snapshot = _write_snapshot(tmp_path, attachment_count=2)
    summary = FakeEnhancer(
        snapshot,
        run_id="run-mixed",
        statuses=["failed", "success"],
    ).run()
    entry = _manifest(snapshot)

    assert summary["status_counts"] == {"failed": 1, "success": 1}
    assert entry["selected_artifact"] == "docling"
    assert entry["fallback_used"] is True
    assert [item["parse_status"] for item in entry["document_enhancements"]] == [
        "failed",
        "success",
    ]


def test_adapter_rejects_escaping_selected_artifact_and_uses_baseline(tmp_path):
    snapshot = _write_snapshot(tmp_path)
    entry = _manifest(snapshot)
    entry.update(
        {
            "selected_artifact": "docling",
            "selected_artifact_path": "../outside.md",
            "parser": "docling",
            "parse_status": "success",
        }
    )
    (snapshot / "_clean_manifest.json").write_text(
        json.dumps([entry], ensure_ascii=False),
        encoding="utf-8",
    )

    document = PolicyCrawl4AIData(snapshot).documents()[0]

    assert document.parser == "baseline"
    assert document.selected_artifact == "clean/policy.md"


def test_incomplete_snapshot_is_rejected_without_manifest_write(tmp_path):
    snapshot = tmp_path / "snapshot-incomplete"
    snapshot.mkdir()
    (snapshot / "_raw_manifest.json").write_text("[]", encoding="utf-8")
    (snapshot / "_clean_manifest.json").write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="Incomplete policy snapshot"):
        PolicyDocumentEnhancer(snapshot).run()


def test_excluded_record_is_audited_without_calling_worker(tmp_path):
    snapshot = _write_snapshot(tmp_path)
    entry = _manifest(snapshot)
    entry["included"] = False
    entry["clean_file"] = ""
    (snapshot / "_clean_manifest.json").write_text(
        json.dumps([entry], ensure_ascii=False),
        encoding="utf-8",
    )
    enhancer = FakeEnhancer(snapshot, run_id="run-excluded")

    summary = enhancer.run()
    updated = _manifest(snapshot)

    assert enhancer.calls == 0
    assert summary["status_counts"] == {"not_routed": 1}
    assert updated["included"] is False
    assert updated["document_enhancements"][0]["route_reasons"] == [
        "record_excluded"
    ]


def test_windows_utf8_bom_manifests_are_supported(tmp_path):
    snapshot = _write_snapshot(tmp_path)
    raw_manifest = (snapshot / "_raw_manifest.json").read_bytes()
    clean_manifest = (snapshot / "_clean_manifest.json").read_bytes()
    (snapshot / "_raw_manifest.json").write_bytes(b"\xef\xbb\xbf" + raw_manifest)
    (snapshot / "_clean_manifest.json").write_bytes(
        b"\xef\xbb\xbf" + clean_manifest
    )

    summary = FakeEnhancer(snapshot, run_id="run-bom").run()

    assert summary["status_counts"] == {"success": 1}


def test_policy_agent_online_node_still_uses_tool_gateway(monkeypatch):
    from app.langgraph.nodes import policy_nodes

    calls = []

    class FakeGateway:
        def invoke(self, agent_name, tool_name, params):
            calls.append((agent_name, tool_name, params))
            return SimpleNamespace(
                status="success",
                data={"chunks": [], "mode": "crawl4ai"},
            )

    monkeypatch.setattr(policy_nodes, "tg", FakeGateway())
    state = {
        "query": "机器人政策",
        "tools_used": [],
        "data_sources": [],
        "status": "searching",
    }

    result = policy_nodes.vector_search_node(state)

    assert calls[0][0:2] == ("PolicyAgent", "policy_hybrid_search")
    assert result["tools_used"] == ["policy_hybrid_search"]


def test_policy_agent_online_node_has_no_docling_or_ingestion_dependency():
    from app.langgraph.nodes import policy_nodes

    source = inspect.getsource(policy_nodes).lower()

    assert "docling" not in source
    assert "policy_document_enhancement" not in source
    assert "policy_ingestion" not in source
    assert "subprocess" not in source
