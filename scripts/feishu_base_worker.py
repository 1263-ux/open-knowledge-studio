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
) -> dict[str, Any]:
    script = config.connector_repo / "scripts" / "raw_bundle_adapter.py"
    result = subprocess.run(
        [
            str(config.connector_python),
            str(script),
            "finalize-v2",
            str(output),
            "--capture-envelope",
            str(capture_path),
            "--processing-run",
            str(run_path),
        ],
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


def initial_run(run_id: str, capture: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "oks-processing-run/v0.2",
        "run_id": run_id,
        "parent_run_id": None,
        "capture_id": capture["capture_id"],
        "recipe_version": "feishu-web-v0.1",
        "job": {
            "namespace": "open-knowledge-studio",
            "name": "feishu-base-to-raw",
            "version": "0.1.0",
            "capability": "web.trafilatura",
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
            "text": {"status": "pending", "capability": "web.trafilatura", "error_code": None, "evidence_count": 0},
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


def process_record(config: WorkerConfig, record: dict[str, Any]) -> dict[str, Any]:
    record_id = record["record_id"]
    fields = record["fields"]
    url = extract_url(fields.get("内容"))
    run_id = f"run-{datetime.now():%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    capture = capture_envelope(config, record_id, fields)
    source_hash = capture["content_hash"]
    run_dir = ROOT / ".oks" / "runs" / run_id
    run = initial_run(run_id, capture)
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

    if not str(receipt.get("content_type", "")).lower().startswith("text/html"):
        error = {"code": "UNSUPPORTED_FETCH_ROUTE", "message": "首版 Worker 仅自动打包公开 HTML；其他格式交给已有模态路由"}
        finish_run(run, "failed", disposition="needs_user_action", error=error)
        atomic_write_json(run_dir / "processing-run.json", run)
        update_record(config, record_id, {"运行状态": "需人工", "错误码": error["code"], "错误说明": error["message"]})
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
    candidates = [record for record in list_records(config, args.limit) if is_candidate(record)]
    if not candidates:
        print(json.dumps({"processed": False, "reason": "no_pending_records"}, ensure_ascii=False))
        return 0
    result = process_record(config, candidates[0])
    print(json.dumps({"processed": True, "run": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
