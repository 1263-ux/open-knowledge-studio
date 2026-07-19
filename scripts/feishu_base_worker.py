"""Feishu Base source adapter for the Open Knowledge Studio Raw pipeline.

This worker owns orchestration only: it reads capture rows, calls the connector
for safe URL probing, delegates extraction to existing Studio adapters, and
writes honest lifecycle state back to Base. It does not bypass authentication,
CAPTCHAs, robots controls, or platform restrictions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any
import uuid


ROOT = Path(__file__).resolve().parents[1]
URL_RE = re.compile(r"https?://[^\s<>\]\[)]+", re.IGNORECASE)
RETRYABLE_CODES = {"RATE_LIMITED", "UPSTREAM_UNAVAILABLE", "NETWORK_ERROR", "TIMEOUT"}


@dataclass(frozen=True)
class WorkerConfig:
    base_token: str
    table_id: str
    lark_cli: Path
    connector_repo: Path
    connector_python: Path
    output_root: Path
    identity: str = "user"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def resolve_lark_cli() -> Path:
    configured = os.environ.get("LARK_CLI_EXE")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(
            Path(appdata)
            / "npm"
            / "node_modules"
            / "@larksuite"
            / "cli"
            / "bin"
            / "lark-cli.exe"
        )
    located = shutil.which("lark-cli.exe")
    if located:
        candidates.append(Path(located))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError("lark-cli.exe not found; set LARK_CLI_EXE to its absolute path")


def load_config(args: argparse.Namespace) -> WorkerConfig:
    base_token = args.base_token or os.environ.get("OKS_FEISHU_BASE_TOKEN")
    table_id = args.table_id or os.environ.get("OKS_FEISHU_TABLE_ID")
    if not base_token or not table_id:
        raise RuntimeError(
            "Base coordinates are required via --base-token/--table-id or "
            "OKS_FEISHU_BASE_TOKEN/OKS_FEISHU_TABLE_ID"
        )
    connector_repo = Path(
        args.connector_repo
        or os.environ.get("OKS_CONNECTOR_REPO", ROOT.parent / "oks-connector")
    ).expanduser().resolve()
    connector_python = Path(
        args.connector_python
        or os.environ.get(
            "OKS_CONNECTOR_PYTHON",
            connector_repo / ".venv-document" / "Scripts" / "python.exe",
        )
    ).expanduser().resolve()
    if not connector_python.is_file():
        raise RuntimeError(f"connector Python not found: {connector_python}")
    return WorkerConfig(
        base_token=base_token,
        table_id=table_id,
        lark_cli=resolve_lark_cli(),
        connector_repo=connector_repo,
        connector_python=connector_python,
        output_root=Path(args.output_root or ROOT / ".oks" / "intake").expanduser().resolve(),
    )


def parse_json_output(result: subprocess.CompletedProcess[str], *, allow_codes: set[int] = {0}) -> dict[str, Any]:
    if result.returncode not in allow_codes:
        raise RuntimeError(
            f"command failed ({result.returncode}): {(result.stderr or result.stdout).strip()}"
        )
    text = result.stdout.strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"command returned non-JSON output: {text[:400]}") from error
    if not isinstance(value, dict):
        raise RuntimeError("command returned a non-object JSON value")
    return value


def lark_json(config: WorkerConfig, *arguments: str) -> dict[str, Any]:
    result = subprocess.run(
        [str(config.lark_cli), *arguments],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    value = parse_json_output(result)
    if value.get("ok") is not True:
        raise RuntimeError(f"lark-cli operation failed: {json.dumps(value, ensure_ascii=False)}")
    return value


def base_args(config: WorkerConfig) -> list[str]:
    return [
        "--base-token",
        config.base_token,
        "--table-id",
        config.table_id,
        "--as",
        config.identity,
    ]


def update_record(config: WorkerConfig, record_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    return lark_json(
        config,
        "base",
        "+record-upsert",
        *base_args(config),
        "--record-id",
        record_id,
        "--json",
        json.dumps(patch, ensure_ascii=False, separators=(",", ":")),
    )


def create_record(config: WorkerConfig, fields: dict[str, Any]) -> dict[str, Any]:
    return lark_json(
        config,
        "base",
        "+record-upsert",
        *base_args(config),
        "--json",
        json.dumps(fields, ensure_ascii=False, separators=(",", ":")),
    )


def list_records(config: WorkerConfig, limit: int = 100) -> list[dict[str, Any]]:
    projection = ["内容", "思考", "附件", "运行状态", "运行ID", "来源哈希", "重试"]
    command = [
        "base",
        "+record-list",
        *base_args(config),
        "--limit",
        str(limit),
        "--format",
        "json",
    ]
    for field in projection:
        command.extend(["--field-id", field])
    envelope = lark_json(config, *command)
    data = envelope.get("data", {})
    fields = data.get("fields", projection)
    rows = data.get("data", [])
    record_ids = data.get("record_id_list", [])
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        record_id = record_ids[index] if index < len(record_ids) else None
        if isinstance(row, list):
            values = dict(zip(fields, row))
        elif isinstance(row, dict):
            record_id = row.get("record_id") or row.get("id") or record_id
            values = row.get("fields", row)
        else:
            continue
        if record_id:
            records.append({"record_id": record_id, "fields": values})
    return records


def is_candidate(record: dict[str, Any]) -> bool:
    fields = record["fields"]
    status = scalar_cell(fields.get("运行状态"))
    retry = fields.get("重试") is True
    return status in (None, "", "待处理") or retry


def scalar_cell(value: object) -> object:
    """Normalize Base single-select reads without changing multi-value fields."""
    if isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


def extract_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    match = URL_RE.search(value)
    return match.group(0).rstrip(".,;，。；") if match else None


def normalize_attachments(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    attachments: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        token = item.get("file_token") or item.get("token") or item.get("id")
        name = item.get("name") or item.get("file_name") or str(token or "attachment")
        attachments.append(
            {
                "source_token": str(token or name),
                "name": str(name),
                "size": int(item.get("size") or 0),
                "mime_type": item.get("mime_type") or item.get("type"),
                "sha256": item.get("sha256"),
                "source_uri": item.get("url") or item.get("tmp_url"),
            }
        )
    return sorted(attachments, key=lambda item: (item["source_token"], item["name"]))


def capture_content_hash(fields: dict[str, Any]) -> str:
    canonical = {
        "source_type": "feishu_base",
        "source_uri": extract_url(fields.get("内容")),
        "content": fields.get("内容"),
        "user_note": fields.get("思考"),
        "attachments": normalize_attachments(fields.get("附件")),
    }
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def envelope_content_hash(capture: dict[str, Any]) -> str:
    canonical = {
        "source_type": capture["source_type"],
        "source_uri": extract_url(capture.get("content")),
        "content": capture.get("content"),
        "user_note": capture.get("user_note"),
        "attachments": capture.get("attachments", []),
        "source_snapshot": capture.get("source_snapshot"),
    }
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def capture_envelope(config: WorkerConfig, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    content_hash = capture_content_hash(fields)
    return {
        "schema_version": "oks-capture-envelope/v0.2",
        "capture_id": f"feishu-{record_id}-{content_hash[:12]}",
        "capture_revision": 1,
        "source_type": "feishu_base",
        "source_uri": f"feishu-base://{config.base_token}/{config.table_id}/{record_id}",
        "captured_at": utc_now(),
        "submitted_by": None,
        "user_note": fields.get("思考"),
        "content": fields.get("内容"),
        "content_hash": content_hash,
        "hash_algorithm": "sha256-canonical-json-v1",
        "source_record": {
            "base_token": config.base_token,
            "table_id": config.table_id,
            "record_id": record_id,
            "revision": None,
        },
        "attachments": normalize_attachments(fields.get("附件")),
        "capture_adapter": {"name": "feishu.base", "version": "0.1.0"},
    }


def probe_source(config: WorkerConfig, url: str) -> dict[str, Any]:
    script = config.connector_repo / "scripts" / "raw_bundle_adapter.py"
    result = subprocess.run(
        [str(config.connector_python), str(script), "probe", url],
        cwd=config.connector_repo,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return parse_json_output(result, allow_codes={0, 2})


def content_type_extension(content_type: str | None) -> str:
    return {
        "application/pdf": ".pdf",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
        "image/tiff": ".tiff",
        "audio/mpeg": ".mp3",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mp4": ".m4a",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
    }.get((content_type or "").split(";", 1)[0].strip().lower(), "")


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
    script = config.connector_repo / "scripts" / "raw_bundle_adapter.py"
    result = subprocess.run(
        [
            str(config.connector_python),
            str(script),
            "fetch",
            url,
            "--output",
            str(target),
            "--overwrite",
        ],
        cwd=config.connector_repo,
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


def attachment_capability(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}:
        return "image.rapidocr", "ocr"
    if suffix == ".pdf":
        return "pdf.mineru", "text"
    if suffix in {".mp4", ".webm", ".mov", ".mkv", ".avi"}:
        return "video.watch", "asr"
    if suffix in {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}:
        return "audio.faster-whisper", "asr"
    return "office.markitdown", "text"


def package_local_attachment(config: WorkerConfig, source: Path, output: Path) -> dict[str, Any]:
    if output.is_dir():
        validation = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "raw_bundle_adapter.py"), "validate", str(output)],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        report = parse_json_output(validation)
        if report.get("valid") is True:
            return report
        raise RuntimeError(f"existing attachment output is invalid: {json.dumps(report, ensure_ascii=False)}")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "raw_ingest.py"),
            "ingest",
            str(source),
            "--output",
            str(output),
            "--benchmark",
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    validation = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "raw_bundle_adapter.py"), "validate", str(output)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    report = parse_json_output(validation)
    if report.get("valid") is not True:
        raise RuntimeError(f"attachment Raw validation failed: {json.dumps(report, ensure_ascii=False)}")
    return report


def package_public_web(
    config: WorkerConfig,
    url: str,
    output: Path,
    human_context: str,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "experiments" / "web_raw_probe.py"),
        url,
        "--output",
        str(output),
        "--human-context",
        human_context or "omitted",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    validation = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "raw_bundle_adapter.py"), "validate", str(output)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    report = parse_json_output(validation)
    if report.get("valid") is not True:
        raise RuntimeError(f"Raw Bundle validation failed: {json.dumps(report, ensure_ascii=False)}")
    return report


def finalize_raw_v2(
    config: WorkerConfig,
    output: Path,
    capture_path: Path,
    run_path: Path,
    source_path: Path | None = None,
) -> dict[str, Any]:
    script = config.connector_repo / "scripts" / "raw_bundle_adapter.py"
    command = [
            str(config.connector_python),
            str(script),
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
        cwd=config.connector_repo,
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
) -> None:
    run["status"] = status
    run["failure_disposition"] = disposition
    run["finished_at"] = utc_now()
    if error:
        run["errors"].append({"code": error["code"], "message": error["message"], "modality": "text"})
        run["modalities"]["text"].update({"status": "failed", "error_code": error["code"]})


def complete_browser_snapshot(config: WorkerConfig, record_id: str, snapshot_dir: Path) -> dict[str, Any]:
    snapshot_dir = snapshot_dir.expanduser().resolve()
    html = snapshot_dir / "rendered.html"
    screenshot = snapshot_dir / "screenshot.png"
    snapshot_manifest = snapshot_dir / "snapshot.json"
    for required in (html, screenshot, snapshot_manifest):
        if not required.is_file():
            raise FileNotFoundError(required)
    snapshot = json.loads(snapshot_manifest.read_text(encoding="utf-8"))
    records = list_records(config, 100)
    record = next((item for item in records if item["record_id"] == record_id), None)
    if record is None:
        raise RuntimeError(f"Base record not found in current table: {record_id}")
    fields = record["fields"]
    source_url = extract_url(fields.get("内容"))
    if not source_url:
        raise RuntimeError("Base record has no HTTP(S) URL")
    snapshot_url = str(snapshot.get("url") or "").split("#", 1)[0].rstrip("/")
    if snapshot_url != source_url.split("#", 1)[0].rstrip("/"):
        raise RuntimeError("browser snapshot URL does not match the Base record URL")

    run_id = f"run-{datetime.now():%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    capture = capture_envelope(config, record_id, fields)
    capture["source_snapshot"] = {
        "final_url": str(snapshot["url"]),
        "content_type": "text/html",
        "size": html.stat().st_size,
        "sha256": sha256_file(html),
    }
    source_hash = envelope_content_hash(capture)
    capture["content_hash"] = source_hash
    capture["capture_id"] = f"feishu-{record_id}-{source_hash[:12]}"
    run = initial_run(run_id, capture, "web.browser-snapshot")
    run["recipe_version"] = "feishu-browser-snapshot-v0.1"
    run["modalities"]["text"].update({"status": "running", "capability": "web.browser-snapshot"})
    run_dir = ROOT / ".oks" / "runs" / run_id
    atomic_write_json(run_dir / "capture-envelope.json", capture)
    atomic_write_json(run_dir / "processing-run.json", run)
    update_record(
        config,
        record_id,
        {
            "运行状态": "已领取",
            "运行ID": run_id,
            "来源哈希": source_hash,
            "采集模式": "公开浏览器",
            "错误码": None,
            "错误说明": None,
            "重试": False,
        },
    )
    try:
        output = config.output_root / f"feishu-{record_id}-{source_hash[:10]}-browser"
        report = package_local_attachment(config, html, output)
        assets = output / "assets"
        derived = output / "derived"
        assets.mkdir(exist_ok=True)
        derived.mkdir(exist_ok=True)
        shutil.copy2(screenshot, assets / "browser-screenshot.png")
        shutil.copy2(snapshot_manifest, derived / "browser-snapshot.json")
        evidence_path = output / "evidence.jsonl"
        existing_evidence = [
            json.loads(line)
            for line in evidence_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        existing_evidence.append(
            {
                "id": "browser-screenshot-0001",
                "kind": "browser_screenshot",
                "text": str(snapshot.get("title") or "Rendered browser snapshot"),
                "method": "browser.public",
                "locator": {"asset": "assets/browser-screenshot.png", "url": snapshot["url"]},
            }
        )
        evidence_path.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in existing_evidence),
            encoding="utf-8",
            newline="\n",
        )
        quality_path = output / "quality-report.json"
        quality_report = json.loads(quality_path.read_text(encoding="utf-8"))
        quality_report["evidence_count"] = len(existing_evidence)
        quality_report.setdefault("coverage_checks", {})["browser_screenshot"] = {
            "expected": 1,
            "observed": 1,
            "status": "passed",
        }
        atomic_write_json(quality_path, quality_report)
        metadata_path = output / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["capture_envelope"] = capture
        metadata["browser_snapshot"] = {
            "manifest": "derived/browser-snapshot.json",
            "screenshot": "assets/browser-screenshot.png",
        }
        atomic_write_json(metadata_path, metadata)
        quality = report.get("processing_status") or metadata.get("processing_status") or "partial"
        run["modalities"]["text"].update({"status": "succeeded", "evidence_count": len(existing_evidence)})
        run["outputs"] = [{"dataset_id": f"bundle:{capture['capture_id']}", "uri": str(output), "kind": "bundle", "sha256": None}]
        finish_run(run, "complete" if quality == "complete" else "partial")
        atomic_write_json(run_dir / "processing-run.json", run)
        finalize_raw_v2(config, output, run_dir / "capture-envelope.json", run_dir / "processing-run.json", html)
        update_record(
            config,
            record_id,
            {
                "运行状态": "Raw就绪",
                "采集模式": "公开浏览器",
                "Raw Bundle": str(output),
                "质量状态": quality,
                "错误码": None,
                "错误说明": None,
                "总结": f"公开 JavaScript 页面已从受控浏览器快照生成 Raw Bundle v0.2；质量状态={quality}。",
            },
        )
        return run
    except Exception as error:
        failure = {"code": "BROWSER_SNAPSHOT_PROCESSING_FAILED", "message": str(error)}
        run["outputs"] = []
        finish_run(run, "failed", disposition="retryable", error=failure)
        atomic_write_json(run_dir / "processing-run.json", run)
        update_record(
            config,
            record_id,
            {
                "运行状态": "可重试失败",
                "采集模式": "公开浏览器",
                "错误码": failure["code"],
                "错误说明": failure["message"][:500],
                "质量状态": "failed",
                "Raw Bundle": None,
            },
        )
        return run


def process_record(config: WorkerConfig, record: dict[str, Any]) -> dict[str, Any]:
    record_id = record["record_id"]
    fields = record["fields"]
    url = extract_url(fields.get("内容"))
    attachment_descriptors = normalize_attachments(fields.get("附件"))
    run_id = f"run-{datetime.now():%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    capture = capture_envelope(config, record_id, fields)
    source_hash = capture["content_hash"]
    run_dir = ROOT / ".oks" / "runs" / run_id
    declared_capability = "web.trafilatura"
    if not url and attachment_descriptors:
        declared_capability, _ = attachment_capability(Path(attachment_descriptors[0]["name"]))
    run = initial_run(run_id, capture, declared_capability)
    atomic_write_json(run_dir / "capture-envelope.json", capture)
    atomic_write_json(run_dir / "processing-run.json", run)
    update_record(
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
    if not url and attachment_descriptors:
        try:
            downloaded = download_attachments(config, record_id, run_dir / "source-downloads")
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
            update_record(config, record_id, {"运行状态": "探测中", "来源哈希": source_hash, "采集模式": "附件"})
            safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", source.stem).strip("-.") or "attachment"
            output = config.output_root / f"feishu-{record_id}-{source_hash[:10]}-{safe_stem}"
            report = package_local_attachment(config, source, output)
            metadata_path = output / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["capture_envelope"] = capture
            atomic_write_json(metadata_path, metadata)
            quality = report.get("processing_status") or metadata.get("processing_status") or "partial"
            evidence_count = int(report.get("evidence_count") or 0)
            run["modalities"][modality].update({"status": "succeeded", "evidence_count": evidence_count})
            run["outputs"] = [{"dataset_id": f"bundle:{capture['capture_id']}", "uri": str(output), "kind": "bundle", "sha256": None}]
            finish_run(run, "complete" if quality == "complete" else "partial")
            atomic_write_json(run_dir / "processing-run.json", run)
            finalize_raw_v2(
                config,
                output,
                run_dir / "capture-envelope.json",
                run_dir / "processing-run.json",
                source,
            )
            update_record(
                config,
                record_id,
                {
                    "运行状态": "Raw就绪",
                    "采集模式": "附件",
                    "Raw Bundle": str(output),
                    "质量状态": quality,
                    "错误码": None,
                    "错误说明": None,
                    "总结": f"附件 Raw Bundle v0.2 已生成并通过校验；能力={capability}；质量状态={quality}。",
                },
            )
        except Exception as error:
            failure = {"code": "ATTACHMENT_PROCESSING_FAILED", "message": str(error)}
            run["outputs"] = []
            finish_run(run, "failed", disposition="retryable", error=failure)
            atomic_write_json(run_dir / "processing-run.json", run)
            update_record(
                config,
                record_id,
                {
                    "运行状态": "可重试失败",
                    "采集模式": "附件",
                    "错误码": failure["code"],
                    "错误说明": failure["message"][:500],
                    "质量状态": "failed",
                    "Raw Bundle": None,
                    "总结": f"附件未生成 Raw：{failure['message']}"[:1000],
                },
            )
        return run

    if not url:
        error = {"code": "UNSUPPORTED_SOURCE", "message": "内容字段中没有 HTTP(S) URL"}
        finish_run(run, "failed", disposition="final", error=error)
        atomic_write_json(run_dir / "processing-run.json", run)
        update_record(
            config,
            record_id,
            {"运行状态": "最终失败", "错误码": error["code"], "错误说明": error["message"], "质量状态": "failed"},
        )
        return run

    update_record(config, record_id, {"运行状态": "探测中"})
    run["modalities"]["text"]["status"] = "running"
    receipt = probe_source(config, url)
    atomic_write_json(run_dir / "fetch-receipt.json", receipt)
    if receipt.get("status") != "ok":
        source_error = receipt.get("error") or {}
        code = source_error.get("code", "FETCH_FAILED")
        message = source_error.get("message", "链接探测未成功")
        if receipt.get("status") == "needs_user_action":
            state = "需授权" if code in {"AUTH_REQUIRED", "CHALLENGE_REQUIRED"} else "需人工"
        elif code in RETRYABLE_CODES:
            state = "可重试失败"
        else:
            state = "最终失败"
        error = {"code": code, "message": message}
        disposition = {
            "需授权": "needs_user_auth",
            "需人工": "needs_user_action",
            "可重试失败": "retryable",
            "最终失败": "final",
        }[state]
        finish_run(run, "failed", disposition=disposition, error=error)
        atomic_write_json(run_dir / "processing-run.json", run)
        update_record(
            config,
            record_id,
            {
                "运行状态": state,
                "采集模式": "登录浏览器" if state == "需授权" else "HTTP",
                "错误码": code,
                "错误说明": message[:500],
                "质量状态": "failed",
                "Raw Bundle": None,
                "总结": f"未生成 Raw：{code}。{message}"[:1000],
            },
        )
        return run

    if (receipt.get("error") or {}).get("code") == "JS_RENDER_REQUIRED" or receipt.get("next_action") == "browser_public":
        error = {
            "code": "JS_RENDER_REQUIRED",
            "message": "公开页面需要浏览器执行 JavaScript；等待受控浏览器快照后继续",
        }
        finish_run(run, "failed", disposition="needs_user_action", error=error)
        atomic_write_json(run_dir / "processing-run.json", run)
        update_record(
            config,
            record_id,
            {
                "运行状态": "需人工",
                "采集模式": "公开浏览器",
                "错误码": error["code"],
                "错误说明": error["message"],
                "质量状态": "failed",
                "Raw Bundle": None,
                "总结": "HTTP 探测确认需要 JavaScript；尚未生成 Raw，等待公开浏览器快照。",
            },
        )
        return run

    if not str(receipt.get("content_type", "")).lower().startswith("text/html"):
        try:
            source, acquisition = download_public_source(config, url, receipt, run_dir / "source-downloads")
            atomic_write_json(run_dir / "acquisition-receipt.json", acquisition)
            capability, modality = attachment_capability(source)
            if capability == "office.markitdown" and source.suffix.lower() not in {".pptx", ".docx", ".xlsx", ".html", ".htm", ".txt", ".csv"}:
                raise RuntimeError(f"unsupported downloaded source format: {source.suffix or 'unknown'}")
            capture["source_snapshot"] = {
                "final_url": str(acquisition.get("final_url") or url),
                "content_type": acquisition.get("content_type"),
                "size": int(acquisition.get("downloaded_bytes") or source.stat().st_size),
                "sha256": str(acquisition.get("content_sha256") or sha256_file(source)),
            }
            source_hash = envelope_content_hash(capture)
            capture["content_hash"] = source_hash
            capture["capture_id"] = f"feishu-{record_id}-{source_hash[:12]}"
            run["capture_id"] = capture["capture_id"]
            run["recipe_version"] = "feishu-public-file-v0.1"
            run["job"]["capability"] = capability
            run["inputs"] = [{"dataset_id": capture["capture_id"], "uri": capture["source_uri"], "kind": "capture", "sha256": source_hash}]
            run["modalities"]["text"]["status"] = "skipped" if modality != "text" else "running"
            run["modalities"][modality].update({"status": "running", "capability": capability})
            atomic_write_json(run_dir / "capture-envelope.json", capture)
            atomic_write_json(run_dir / "processing-run.json", run)
            update_record(config, record_id, {"运行状态": "探测中", "来源哈希": source_hash, "采集模式": "HTTP"})
            output = config.output_root / f"feishu-{record_id}-{source_hash[:10]}-{source.stem}"
            report = package_local_attachment(config, source, output)
            metadata_path = output / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["capture_envelope"] = capture
            metadata["fetch_receipt"] = str((run_dir / "fetch-receipt.json").resolve())
            metadata["acquisition_receipt"] = str((run_dir / "acquisition-receipt.json").resolve())
            atomic_write_json(metadata_path, metadata)
            quality = report.get("processing_status") or metadata.get("processing_status") or "partial"
            evidence_count = int(report.get("evidence_count") or 0)
            run["modalities"][modality].update({"status": "succeeded", "evidence_count": evidence_count})
            run["outputs"] = [{"dataset_id": f"bundle:{capture['capture_id']}", "uri": str(output), "kind": "bundle", "sha256": None}]
            finish_run(run, "complete" if quality == "complete" else "partial")
            atomic_write_json(run_dir / "processing-run.json", run)
            finalize_raw_v2(config, output, run_dir / "capture-envelope.json", run_dir / "processing-run.json", source)
            update_record(
                config,
                record_id,
                {
                    "运行状态": "Raw就绪",
                    "采集模式": "HTTP",
                    "Raw Bundle": str(output),
                    "质量状态": quality,
                    "错误码": None,
                    "错误说明": None,
                    "总结": f"公网文件 Raw Bundle v0.2 已生成并通过校验；能力={capability}；质量状态={quality}。",
                },
            )
        except Exception as error:
            failure = {"code": "PUBLIC_FILE_PROCESSING_FAILED", "message": str(error)}
            run["outputs"] = []
            finish_run(run, "failed", disposition="retryable", error=failure)
            atomic_write_json(run_dir / "processing-run.json", run)
            update_record(
                config,
                record_id,
                {
                    "运行状态": "可重试失败",
                    "采集模式": "HTTP",
                    "错误码": failure["code"],
                    "错误说明": failure["message"][:500],
                    "质量状态": "failed",
                    "Raw Bundle": None,
                    "总结": f"公网文件未生成 Raw：{failure['message']}"[:1000],
                },
            )
        return run

    output = config.output_root / f"feishu-{record_id}-{source_hash[:10]}"
    try:
        report = package_public_web(config, url, output, str(fields.get("思考") or ""))
        metadata_path = output / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["capture_envelope"] = capture
        metadata["fetch_receipt"] = str((run_dir / "fetch-receipt.json").resolve())
        atomic_write_json(metadata_path, metadata)
        quality = report.get("processing_status") or metadata.get("processing_status") or "partial"
        evidence_count = int(report.get("evidence_count") or 0)
        run["modalities"]["text"].update({"status": "succeeded", "evidence_count": evidence_count})
        run["outputs"] = [{"dataset_id": f"bundle:{capture['capture_id']}", "uri": str(output), "kind": "bundle", "sha256": None}]
        finish_run(run, "complete" if quality == "complete" else "partial")
        atomic_write_json(run_dir / "processing-run.json", run)
        finalize_raw_v2(
            config,
            output,
            run_dir / "capture-envelope.json",
            run_dir / "processing-run.json",
        )
        update_record(
            config,
            record_id,
            {
                "运行状态": "Raw就绪",
                "采集模式": "HTTP",
                "Raw Bundle": str(output),
                "质量状态": quality,
                "错误码": None,
                "错误说明": None,
                "总结": f"Raw Bundle v0.2 已生成并通过校验；质量状态={quality}。",
            },
        )
    except Exception as error:
        failure = {"code": "EXTRACTION_FAILED", "message": str(error)}
        finish_run(run, "failed", disposition="retryable", error=failure)
        atomic_write_json(run_dir / "processing-run.json", run)
        update_record(
            config,
            record_id,
            {
                "运行状态": "可重试失败",
                "采集模式": "HTTP",
                "错误码": failure["code"],
                "错误说明": failure["message"][:500],
                "质量状态": "failed",
                "Raw Bundle": None,
                "总结": f"未生成 Raw：{failure['code']}。{failure['message']}"[:1000],
            },
        )
    return run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-token")
    parser.add_argument("--table-id")
    parser.add_argument("--connector-repo")
    parser.add_argument("--connector-python")
    parser.add_argument("--output-root")
    subcommands = parser.add_subparsers(dest="command", required=True)
    enqueue = subcommands.add_parser("enqueue", help="Create one pending capture row.")
    enqueue.add_argument("content")
    enqueue.add_argument("--thought", default="")
    enqueue.add_argument("--rating", choices=("A", "B", "C"))
    once = subcommands.add_parser("run-once", help="Process at most one pending row.")
    once.add_argument("--limit", type=int, default=100)
    browser = subcommands.add_parser("complete-browser", help="Complete one JS-rendered record from a controlled browser snapshot.")
    browser.add_argument("--record-id", required=True)
    browser.add_argument("--snapshot-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args)
    if args.command == "enqueue":
        fields: dict[str, Any] = {
            "内容": args.content,
            "思考": args.thought,
            "状态": "未处理",
            "运行状态": "待处理",
            "Wiki状态": "none",
            "重试": False,
        }
        if args.rating:
            fields["评级"] = args.rating
        print(json.dumps(create_record(config, fields), ensure_ascii=False, indent=2))
        return 0
    if args.command == "complete-browser":
        result = complete_browser_snapshot(config, args.record_id, args.snapshot_dir)
        print(json.dumps({"processed": True, "run": result}, ensure_ascii=False, indent=2))
        return 0 if result.get("status") in {"complete", "partial"} else 2
    candidates = [record for record in list_records(config, args.limit) if is_candidate(record)]
    if not candidates:
        print(json.dumps({"processed": False, "reason": "no_pending_records"}, ensure_ascii=False))
        return 0
    result = process_record(config, candidates[0])
    print(json.dumps({"processed": True, "run": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
