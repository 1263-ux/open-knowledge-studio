"""Feishu worker pipeline — ``process_record`` orchestration and helpers.

.. attention:: ARCHITECTURE DEBT — crosses four architecture planes.

    ``process_record()`` currently performs:
    - Source Plane: read/claim records, extract URLs
    - Acquisition Plane: probe URLs, download attachments
    - Perception Plane: select extractors, call ``oks-connector`` CLI
    - Knowledge Plane: publish candidates, send notifications

    In the target architecture (Phase 6):
    - The **Agent** owns Perception and Knowledge planes via the ingest skill
    - The Worker is limited to Source Plane (record read/claim) and
      Review Control Plane (notification delivery, review consumption)
    - ``source_router.py`` is deprecated and will be deleted
    - ``process_record()`` will be decomposed into:
      ``claim_source()`` + ``await_agent_ingest()`` + ``update_status()``
    - Candidate publication moves to Agent's ``observation_to_candidate()``

    **Current state**: kept only for Source and Review plane operations.
    Packaging and orchestration were removed in Phase 6 (v0.4.0).
    Do NOT add orchestration logic here.

Extracted from feishu_base_worker.py (Round 3 Phase 3).  Imports only from
feishu_worker.* leaf modules and stdlib.  Never imports feishu_base_worker.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from feishu_worker.config import WorkerConfig
from feishu_worker.io_utils import (
    attachment_capability,
    atomic_write_json,
    atomic_write_text,
    content_type_extension,
    _redact_error_text,
    sha256_file,
    utc_now,
)
from feishu_worker.base_client import (
    RETRYABLE_CODES,
    parse_json_output,
    lark_json as _base_client_lark_json,
    base_args as _base_client_base_args,
)
from feishu_worker.capture import (
    extract_url,
    normalize_attachments,
    capture_envelope,
    envelope_content_hash,
)

# ── Packaging stubs: source_router.py was permanently deleted in Phase 6. ──
# The old oks-connector packaging pipeline is gone.  These stubs exist only
# so process_record() still loads — they raise immediately if any code path
# tries to reach the old packaging logic.  There is NO env-var gate to
# restore this functionality.  Use Agent-native ingest with oks raw-commit,
# or checkout Git tag v0.4.0-legacy-final for the old pipeline.


def _connector_binary() -> list[str]:
    raise NotImplementedError(
        "source_router was permanently deleted in OKS 0.4.0. "
        "No env-var gate exists. Use Agent-native ingest with oks raw-commit. "
        "The old code is preserved in Git tag v0.4.0-legacy-final."
    )


def package_local_attachment(*args: Any, **kwargs: Any) -> Any:
    raise NotImplementedError(
        "source_router was permanently deleted in OKS 0.4.0. "
        "No env-var gate exists. Use Agent-native ingest with oks raw-commit."
    )


def package_routed_source(*args: Any, **kwargs: Any) -> Any:
    raise NotImplementedError(
        "source_router was permanently deleted in OKS 0.4.0. "
        "No env-var gate exists. Use Agent-native ingest with oks raw-commit."
    )


def package_public_web(*args: Any, **kwargs: Any) -> Any:
    raise NotImplementedError(
        "source_router was permanently deleted in OKS 0.4.0. "
        "No env-var gate exists. Use Agent-native ingest with oks raw-commit."
    )


ROOT = Path(
    os.environ.get("OKS_KNOWLEDGE_ROOT")
    or Path(__file__).resolve().parents[2]
).expanduser().resolve()


# ── Thin wrappers (supply ROOT) ──────────────────────────────────────────


def lark_json(config: WorkerConfig, *arguments: str) -> dict[str, Any]:
    return _base_client_lark_json(config, *arguments, root=ROOT)


def base_args(config: WorkerConfig) -> list[str]:
    return _base_client_base_args(config)


# ── Direct helpers for process_record ────────────────────────────────────


def update_record(config: WorkerConfig, record_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Update one Base record via the worker's monkeypatchable lark_json."""
    return lark_json(
        config,
        "base",
        "+record-upsert",
        *_base_client_base_args(config),
        "--record-id",
        record_id,
        "--json",
        json.dumps(patch, ensure_ascii=False, separators=(",", ":")),
    )


def download_attachments(config: WorkerConfig, record_id: str, output: Path) -> list[Path]:
    output = output.resolve()
    try:
        relative_output = output.relative_to(ROOT)
    except ValueError as error:
        raise RuntimeError(f"attachment download target must stay inside Studio: {output}") from error
    output.mkdir(parents=True, exist_ok=True)
    lark_json(
        config,
        "base",
        "+record-download-attachment",
        *base_args(config),
        "--record-id",
        record_id,
        "--output",
        "./" + relative_output.as_posix(),
        "--overwrite",
    )
    return sorted(path for path in output.iterdir() if path.is_file())


def initial_run(run_id: str, capture: dict[str, Any], capability: str = "web.trafilatura") -> dict[str, Any]:
    return {
        "schema_version": "oks-processing-run/v0.2",
        "run_id": run_id,
        "parent_run_id": None,
        "capture_id": capture["capture_id"],
        "recipe_version": "feishu-web-v0.1" if capability == "web.trafilatura" else "feishu-attachment-v0.1",
        "job": {
            "namespace": "open-knowledge-studio",
            "name": "feishu-base-to-raw",
            "version": "0.1.0",
            "capability": capability,
        },
        "started_at": utc_now(),
        "finished_at": None,
        "status": "running",
        "failure_disposition": "none",
        "inputs": [
            {
                "dataset_id": capture["capture_id"],
                "uri": capture["source_uri"],
                "kind": "capture",
                "sha256": capture["content_hash"],
            }
        ],
        "outputs": [],
        "modalities": {
            "text": {"status": "pending", "capability": capability if capability in {"web.trafilatura", "office.markitdown", "pdf.mineru"} else None, "error_code": None, "evidence_count": 0},
            "ocr": {"status": "skipped", "capability": None, "error_code": None, "evidence_count": 0},
            "asr": {"status": "skipped", "capability": None, "error_code": None, "evidence_count": 0},
            "video": {"status": "skipped", "capability": None, "error_code": None, "evidence_count": 0},
            "visual_observation": {"status": "skipped", "capability": None, "error_code": None, "evidence_count": 0},
        },
        "warnings": [],
        "errors": [],
    }


def finish_run(
    run: dict[str, Any],
    status: str,
    *,
    disposition: str = "none",
    error: dict[str, Any] | None = None,
    error_modality: str = "text",
) -> None:
    run["status"] = status
    run["failure_disposition"] = disposition
    run["finished_at"] = utc_now()
    if error:
        run["errors"].append({"code": error["code"], "message": error["message"], "modality": error_modality})
        run["modalities"][error_modality].update({"status": "failed", "error_code": error["code"]})


def finalize_raw_v2(
    config: WorkerConfig,
    output: Path,
    capture_path: Path,
    run_path: Path,
    source_path: Path | None = None,
) -> dict[str, Any]:
    connector = _connector_binary()
    command = [
            *connector,
            "finalize-v2",
            str(output),
            "--capture-envelope",
            str(capture_path),
            "--processing-run",
            str(run_path),
        ]
    if source_path is not None:
        command.extend(["--source", str(source_path)])
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    report = parse_json_output(result)
    if report.get("valid") is not True or report.get("schema_version") != "raw-multimodal/v0.2":
        raise RuntimeError(f"Raw Bundle v0.2 validation failed: {json.dumps(report, ensure_ascii=False)}")
    return report


def probe_source(config: WorkerConfig, url: str) -> dict[str, Any]:
    connector = _connector_binary()
    result = subprocess.run(
        [*connector, "probe", url],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return parse_json_output(result, allow_codes={0, 2})


def download_public_source(
    config: WorkerConfig,
    url: str,
    probe_receipt: dict[str, Any],
    output_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    suffix = Path(str(probe_receipt.get("final_url") or url).split("?", 1)[0]).suffix.lower()
    if not suffix:
        suffix = content_type_extension(probe_receipt.get("content_type"))
    if not suffix:
        raise RuntimeError("public file route has neither a supported URL extension nor MIME type")
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"source{suffix}"
    connector = _connector_binary()
    result = subprocess.run(
        [
            *connector,
            "fetch",
            url,
            "--output",
            str(target),
            "--overwrite",
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    receipt = parse_json_output(result, allow_codes={0, 2})
    if receipt.get("status") != "ok":
        error = receipt.get("error") or {}
        raise RuntimeError(f"{error.get('code', 'FETCH_FAILED')}: {error.get('message', 'source download failed')}")
    downloaded = Path(str(receipt.get("output") or target)).resolve()
    if not downloaded.is_file():
        raise RuntimeError(f"fetch reported success without a source snapshot: {downloaded}")
    return downloaded, receipt


# ── Shared tail helper (attachment error path) ────────────────────────────


def _fail_bundle(
    *,
    config: WorkerConfig,
    record_id: str,
    run: dict[str, Any],
    run_dir: Path,
    error: Exception,
    failure_code: str,
    build_failure_patch: Any,
    _update: Any,
    clear_outputs: bool = True,
) -> None:
    """Failure tail: finish_run, processing-run write, Base update with redaction."""
    failure = {"code": failure_code, "message": str(error)}
    if clear_outputs:
        run["outputs"] = []
    finish_run(run, "failed", disposition="retryable", error=failure)
    atomic_write_json(run_dir / "processing-run.json", run)
    redacted = _redact_error_text(str(error))
    _update(config, record_id, build_failure_patch(failure_code, redacted))


# ── Main pipeline ────────────────────────────────────────────────────────


def process_record(
    config: WorkerConfig,
    record: dict[str, Any],
    *,
    claimed_run_id: str | None = None,
    _update_record: Any = None,
    _download_attachments: Any = None,
) -> dict[str, Any]:
    _update = _update_record if _update_record is not None else update_record
    _dl_att = _download_attachments if _download_attachments is not None else download_attachments

    record_id = record["record_id"]
    fields = record["fields"]
    url = extract_url(fields.get("内容"))
    attachment_descriptors = normalize_attachments(fields.get("附件"))
    inline_text = str(fields.get("内容") or "").strip()
    run_id = claimed_run_id or f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    capture = capture_envelope(config, record_id, fields)
    source_hash = capture["content_hash"]
    run_dir = ROOT / ".oks" / "runs" / run_id
    declared_capability = "web.trafilatura"
    if not url and attachment_descriptors:
        declared_capability, _ = attachment_capability(Path(attachment_descriptors[0]["name"]))
    elif not url and inline_text:
        declared_capability = "office.markitdown"
    run = initial_run(run_id, capture, declared_capability)
    atomic_write_json(run_dir / "capture-envelope.json", capture)
    atomic_write_json(run_dir / "processing-run.json", run)
    _update(
        config,
        record_id,
        {
            "运行状态": "已领取",
            "运行ID": run_id,
            "来源哈希": source_hash,
            "错误码": None,
            "错误说明": None,
            "重试": False,
            "Wiki状态": "none",
        },
    )
    if not url and not attachment_descriptors and inline_text:
        source = run_dir / "submitted-content.txt"
        atomic_write_text(source, inline_text + "\n")
        capture["source_snapshot"] = {
            "kind": "content",
            "content_hash_status": "verified",
            "final_url": capture["source_uri"],
            "content_type": "text/plain; charset=utf-8",
            "size": source.stat().st_size,
            "sha256": sha256_file(source),
        }
        source_hash = envelope_content_hash(capture)
        capture["content_hash"] = source_hash
        capture["capture_id"] = f"feishu-{record_id}-{source_hash[:12]}"
        run["capture_id"] = capture["capture_id"]
        run["recipe_version"] = "feishu-inline-text-v0.1"
        run["job"]["capability"] = "office.markitdown"
        run["inputs"] = [{
            "dataset_id": capture["capture_id"],
            "uri": capture["source_uri"],
            "kind": "capture",
            "sha256": source_hash,
        }]
        run["modalities"]["text"].update({"status": "running", "capability": "office.markitdown"})
        atomic_write_json(run_dir / "capture-envelope.json", capture)
        atomic_write_json(run_dir / "processing-run.json", run)
        _update(
            config,
            record_id,
            {"运行状态": "探测中", "来源哈希": source_hash, "采集模式": "直接文本"},
        )
        # ── Agent handoff ── source_router / oks-connector deleted in v0.4.0.
        # Worker captures source content; Agent completes Raw→Candidate→Publish.
        output = config.output_root / f"feishu-{record_id}-{source_hash[:10]}-inline-text"
        run["outputs"] = [{
            "dataset_id": capture["capture_id"],
            "uri": str(run_dir),
            "kind": "capture_run_dir",
            "sha256": None,
        }]
        finish_run(run, "awaiting_agent", disposition="none")
        atomic_write_json(run_dir / "processing-run.json", run)
        _update(
            config,
            record_id,
            {
                "运行状态": "需人工",
                "采集模式": "直接文本",
                "Raw Bundle": None,
                "质量状态": None,
                "错误码": None,
                "错误说明": None,
                "总结": "文字采集已完成，等待 Agent 生成 Raw Bundle 和 Candidate。",
            },
        )
        return run

    if not url and attachment_descriptors:
        try:
            downloaded = _dl_att(config, record_id, run_dir / "source-downloads")
            if len(downloaded) != 1:
                raise RuntimeError(f"首版附件 Worker 要求恰好 1 个附件，实际下载 {len(downloaded)} 个")
            source = downloaded[0]
            capability, modality = attachment_capability(source)
            capture["attachments"][0]["sha256"] = sha256_file(source)
            source_hash = envelope_content_hash(capture)
            capture["content_hash"] = source_hash
            capture["capture_id"] = f"feishu-{record_id}-{source_hash[:12]}"
            run["capture_id"] = capture["capture_id"]
            run["job"]["capability"] = capability
            run["inputs"] = [{"dataset_id": capture["capture_id"], "uri": capture["source_uri"], "kind": "capture", "sha256": source_hash}]
            run["modalities"]["text"]["status"] = "skipped" if modality != "text" else "running"
            run["modalities"][modality].update({"status": "running", "capability": capability})
            atomic_write_json(run_dir / "capture-envelope.json", capture)
            atomic_write_json(run_dir / "processing-run.json", run)
            _update(config, record_id, {"运行状态": "探测中", "来源哈希": source_hash, "采集模式": "附件"})
            safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", source.stem).strip("-.") or "attachment"
            output = config.output_root / f"feishu-{record_id}-{source_hash[:10]}-{safe_stem}"
            # ── Agent handoff ── source_router/oks-connector deleted in v0.4.0
            run["outputs"] = [{
                "dataset_id": capture["capture_id"],
                "uri": str(run_dir),
                "kind": "capture_run_dir",
                "sha256": None,
            }]
            finish_run(run, "awaiting_agent", disposition="none")
            atomic_write_json(run_dir / "processing-run.json", run)
            _update(
                config,
                record_id,
                {
                    "运行状态": "需人工",
                    "采集模式": "附件",
                    "Raw Bundle": None,
                    "质量状态": None,
                    "错误码": None,
                    "错误说明": None,
                    "总结": f"附件下载完成，等待 Agent 处理（能力={capability}）。",
                },
            )
        except Exception as error:
            _fail_bundle(
                config=config,
                record_id=record_id,
                run=run,
                run_dir=run_dir,
                error=error,
                failure_code="ATTACHMENT_PROCESSING_FAILED",
                build_failure_patch=lambda code, msg: {
                    "运行状态": "可重试失败",
                    "采集模式": "附件",
                    "错误码": code,
                    "错误说明": msg[:500],
                    "质量状态": "failed",
                    "Raw Bundle": None,
                    "总结": f"附件未生成 Raw：{msg}"[:1000],
                },
                _update=_update,
            )
        return run

    if not url:
        error = {"code": "UNSUPPORTED_SOURCE", "message": "内容字段中没有 HTTP(S) URL"}
        finish_run(run, "failed", disposition="final", error=error)
        atomic_write_json(run_dir / "processing-run.json", run)
        _update(
            config,
            record_id,
            {"运行状态": "最终失败", "错误码": error["code"], "错误说明": error["message"], "质量状态": "failed"},
        )
        return run

    # ── Agent handoff ── source_router / oks-connector deleted in v0.4.0.
    # Worker no longer probes, downloads, or packages URLs.  It captures the
    # source URL + metadata; the Agent fetches content with its own tools
    # (WebFetch, Playwright, etc.) and runs raw-commit → publish-candidate.
    source = run_dir / "submitted-url.txt"
    atomic_write_text(source, url + "\n")
    capture["source_snapshot"] = {
        "kind": "reference",
        "content_hash_status": "unavailable",
        "final_url": url,
        "content_type": None,
        "size": source.stat().st_size,
        "sha256": sha256_file(source),
    }
    source_hash = envelope_content_hash(capture)
    capture["content_hash"] = source_hash
    capture["capture_id"] = f"feishu-{record_id}-{source_hash[:12]}"
    run["capture_id"] = capture["capture_id"]
    run["recipe_version"] = "feishu-url-v0.1"
    run["job"]["capability"] = "web.trafilatura"
    run["inputs"] = [{
        "dataset_id": capture["capture_id"],
        "uri": capture["source_uri"],
        "kind": "capture",
        "sha256": source_hash,
    }]
    run["modalities"]["text"].update({"status": "running", "capability": "web.trafilatura"})
    atomic_write_json(run_dir / "capture-envelope.json", capture)
    atomic_write_json(run_dir / "processing-run.json", run)
    _update(
        config,
        record_id,
        {"运行状态": "探测中", "来源哈希": source_hash, "采集模式": "HTTP"},
    )
    run["outputs"] = [{
        "dataset_id": capture["capture_id"],
        "uri": str(run_dir),
        "kind": "capture_run_dir",
        "sha256": None,
    }]
    finish_run(run, "awaiting_agent", disposition="none")
    atomic_write_json(run_dir / "processing-run.json", run)
    _update(
        config,
        record_id,
        {
            "运行状态": "需人工",
            "采集模式": "HTTP",
            "Raw Bundle": None,
            "质量状态": None,
            "错误码": None,
            "错误说明": None,
            "总结": "URL 已捕获，等待 Agent 抓取内容并生成 Raw Bundle 和 Candidate。",
        },
    )
    return run
