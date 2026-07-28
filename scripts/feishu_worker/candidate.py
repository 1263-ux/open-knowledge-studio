"""Feishu worker candidate module — state path/load/save, render/parse, fingerprint, publish.

Extracted from feishu_base_worker.py (Round 3 Phase 5).  Imports only from
feishu_worker.* leaf modules (config, io_utils, base_client) and stdlib.
Never imports feishu_base_worker.  Callers must supply *root* explicitly so
this module has zero dependency on the ROOT constant in the main worker.
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from feishu_worker.config import WorkerConfig, configured_knowledge_root
from feishu_worker.io_utils import (
    atomic_write_json,
    atomic_write_text,
    scalar_cell,
    utc_now,
)
from feishu_worker.base_client import (
    LarkFn,
    base_args,
    get_record as _base_get_record,
    lark_json as _base_lark_json,
    update_record as _base_update_record,
)

# ── Candidate field projection ─────────────────────────────────────────
CANDIDATE_FIELDS = [
    "运行状态",
    "运行ID",
    "Raw Bundle",
    "Wiki状态",
    "候选ID",
    "候选内容",
    "审核动作",
    "审核意见",
    "修改类型",
    "审核时间",
    "Wiki路径",
]


# ── Document parse / render ────────────────────────────────────────────


def parse_candidate_document(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        raise ValueError("Candidate must start with YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise ValueError("Candidate frontmatter is not closed")
    metadata = yaml.safe_load(parts[1].strip()) or {}
    if not isinstance(metadata, dict):
        raise ValueError("Candidate frontmatter must be an object")
    for field in ("title", "draft_type", "draft_area"):
        if not str(metadata.get(field) or "").strip():
            raise ValueError(f"Candidate frontmatter missing {field}")
    if metadata["draft_type"] not in {"concept", "strategy", "anti-pattern"}:
        raise ValueError("Candidate draft_type must be concept, strategy, or anti-pattern")
    body = parts[2].strip()
    if len(body) < 50:
        raise ValueError("Candidate body must contain at least 50 characters")
    return metadata, body


def render_candidate_document(metadata: dict[str, Any], body: str) -> str:
    frontmatter = yaml.safe_dump(
        metadata,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    return f"---\n{frontmatter}---\n\n{body.strip()}\n"


# ── Candidate state path / load ────────────────────────────────────────


def candidate_state_path(record_id: str, *, root: Path) -> Path:
    safe_record_id = re.sub(r"[^A-Za-z0-9_-]+", "-", record_id).strip("-")
    if not safe_record_id:
        raise ValueError("record_id cannot form a Candidate state path")
    return root / ".oks" / "candidates" / f"{safe_record_id}.json"


def load_candidate_state(record_id: str, *, root: Path) -> dict[str, Any]:
    path = candidate_state_path(record_id, root=root)
    if not path.is_file():
        raise FileNotFoundError(f"Candidate state not found for Base record: {record_id}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Candidate state is not an object: {path}")
    return value


# ── Fingerprint ────────────────────────────────────────────────────────


def candidate_review_fingerprint(fields: dict[str, Any]) -> str:
    payload = {
        "action": scalar_cell(fields.get("审核动作")),
        "comment": fields.get("审核意见"),
        "change_types": fields.get("修改类型"),
        "reviewed_at": fields.get("审核时间"),
        "candidate": fields.get("候选内容"),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


# ── Review notification helpers (publish_candidate needs these) ────────


def render_candidate_review_message(
    *,
    record_id: str,
    candidate_id: str,
    revision: int,
    metadata: dict[str, Any],
    body: str,
    fields: dict[str, Any],
) -> str:
    """Render Agent-authored review context without inventing new claims."""
    summary = str(metadata.get("review_summary") or "").strip()
    if not summary:
        summary = body.strip()[:600]
        if len(body.strip()) > 600:
            summary += "\u2026"
    raw_questions = metadata.get("review_questions") or []
    if isinstance(raw_questions, str):
        questions = [raw_questions.strip()] if raw_questions.strip() else []
    elif isinstance(raw_questions, list):
        questions = [str(item).strip() for item in raw_questions if str(item).strip()]
    else:
        questions = []
    question_lines = "\n".join(f"- {item}" for item in questions[:3])
    if not question_lines:
        question_lines = "- 这条知识是否值得进入你的个人知识库？"
    source = str(scalar_cell(fields.get("内容")) or "").strip()
    user_note = str(fields.get("思考") or "").strip()
    context_lines = []
    if source:
        context_lines.append(f"**来源：** {source}")
    if user_note:
        context_lines.append(f"**你的原始思考：** {user_note}")
    context = "\n\n".join(context_lines)
    if context:
        context += "\n\n"
    return (
        "## 知识候选待审核\n\n"
        f"**主题：** {metadata.get('title', candidate_id)}\n\n"
        f"{context}"
        f"**Agent 总结：**\n\n{summary}\n\n"
        f"**需要你判断：**\n\n{question_lines}\n\n"
        "请直接回复以下任一动作：\n\n"
        "- `accept`：接受；可附一句理由\n"
        "- `edit`：说明需要修改什么\n"
        "- `reject`：说明拒绝原因\n"
        "- `defer`：暂缓处理\n\n"
        f"候选标识：`{candidate_id}` · revision `{revision}` · Base `{record_id}`"
    )


def send_candidate_review_notification(
    config: WorkerConfig,
    *,
    record_id: str,
    state: dict[str, Any],
    metadata: dict[str, Any],
    body: str,
    fields: dict[str, Any],
    root: Path,
    _lark_fn: LarkFn | None = None,
) -> dict[str, Any]:
    recipient = config.review_recipient_user_id
    if not recipient:
        return {"status": "skipped", "reason": "review_recipient_not_configured"}
    message = render_candidate_review_message(
        record_id=record_id,
        candidate_id=str(state["candidate_id"]),
        revision=int(state["revision"]),
        metadata=metadata,
        body=body,
        fields=fields,
    )
    idempotency_key = hashlib.sha256(
        f"{state['candidate_id']}:{state['revision']}:{state['candidate_sha256']}".encode("utf-8")
    ).hexdigest()[:50]
    _lark = _lark_fn if _lark_fn is not None else functools.partial(_base_lark_json, root=root)
    try:
        envelope = _lark(
            config,
            "im",
            "+messages-send",
            "--user-id",
            recipient,
            "--markdown",
            message,
            "--idempotency-key",
            idempotency_key,
            "--as",
            config.review_message_identity,
            "--format",
            "json",
        )
    except RuntimeError as error:
        return {"status": "failed", "error": str(error)[:500]}
    data = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
    return {
        "status": "sent",
        "message_id": data.get("message_id") or envelope.get("message_id"),
        "chat_id": data.get("chat_id") or envelope.get("chat_id"),
        "identity": config.review_message_identity,
        "recipient": recipient,
        "idempotency_key": idempotency_key,
    }


# ── Publish candidate ──────────────────────────────────────────────────


def publish_candidate(
    config: WorkerConfig,
    record_id: str,
    candidate_file: Path,
    *,
    root: Path,
    _get_fn: LarkFn | None = None,
    _update_fn: LarkFn | None = None,
    _lark_fn: LarkFn | None = None,
    _send_notification_fn: LarkFn | None = None,
) -> dict[str, Any]:
    _get = _get_fn if _get_fn is not None else functools.partial(_base_get_record, root=root)
    _update = _update_fn if _update_fn is not None else functools.partial(_base_update_record, root=root)
    _lark = _lark_fn if _lark_fn is not None else functools.partial(_base_lark_json, root=root)
    _send_notification = _send_notification_fn if _send_notification_fn is not None else send_candidate_review_notification

    record = _get(config, record_id, [*CANDIDATE_FIELDS, "内容", "思考"])
    fields = record["fields"]
    status = scalar_cell(fields.get("运行状态"))
    if status not in {"Raw就绪", "候选待审", "需人工"}:
        raise RuntimeError(f"Base record is not ready for Candidate publication: {status!r}")
    raw_bundle = scalar_cell(fields.get("Raw Bundle"))
    if not isinstance(raw_bundle, str) or not raw_bundle.strip():
        raise RuntimeError("Base record has no Raw Bundle; refusing to publish Candidate")
    raw_path = Path(raw_bundle).expanduser().resolve()
    if not raw_path.is_dir() or not (raw_path / "bundle.json").is_file():
        raise RuntimeError(f"Raw Bundle is not locally verifiable: {raw_path}")

    source = candidate_file.expanduser().resolve()
    metadata, body = parse_candidate_document(source.read_text(encoding="utf-8"))
    candidate_id = re.sub(r"[^a-z0-9-]+", "-", source.stem.lower()).strip("-")
    if not candidate_id:
        candidate_id = f"feishu-{record_id.lower()}"
    knowledge_root = configured_knowledge_root(config, root=root)
    target = knowledge_root / "drafts" / f"{candidate_id}.md"
    metadata["status"] = "draft"
    source_pages = metadata.get("source_pages", [])
    if not isinstance(source_pages, list):
        source_pages = [str(source_pages)] if source_pages else []
    metadata["source_pages"] = list(dict.fromkeys([
        *source_pages,
        f"feishu:{record_id}",
    ]))
    traces = metadata.get("traces")
    if not isinstance(traces, list):
        traces = []
    manifest = json.loads((raw_path / "bundle.json").read_text(encoding="utf-8"))
    execution_trace: dict[str, Any] = {
        "kind": "execution",
        "id": str(scalar_cell(fields.get("运行ID")) or ""),
    }
    for key in ("capture_id", "bundle_id"):
        value = str(manifest.get(key) or "").strip()
        if value:
            execution_trace[key] = value
    try:
        execution_trace["path"] = raw_path.relative_to(knowledge_root).as_posix()
    except ValueError:
        pass
    trace_values = [
        execution_trace,
        {"kind": "external", "id": f"feishu-base:{record_id}"},
    ]
    for trace in trace_values:
        if trace not in traces:
            traces.append(trace)
    metadata["traces"] = traces
    document = render_candidate_document(metadata, body)
    atomic_write_text(target, document)

    state_path = candidate_state_path(record_id, root=root)
    previous: dict[str, Any] = {}
    if state_path.is_file():
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            previous = loaded
    state = {
        "schema_version": "oks-feishu-candidate/v0.1",
        "record_id": record_id,
        "candidate_id": candidate_id,
        "candidate_path": (
            target.relative_to(root.resolve()).as_posix()
            if knowledge_root == root.resolve()
            else str(target)
        ),
        "candidate_sha256": hashlib.sha256(document.encode("utf-8")).hexdigest(),
        "raw_bundle": str(raw_path),
        "run_id": scalar_cell(fields.get("运行ID")),
        "revision": int(previous.get("revision", 0)) + 1,
        "published_at": utc_now(),
        "review_history": previous.get("review_history", []),
        "last_review_fingerprint": None,
    }
    atomic_write_json(state_path, state)
    _update(
        config,
        record_id,
        {
            "候选ID": candidate_id,
            "候选内容": body,
            "审核动作": None,
            "审核意见": None,
            "修改类型": None,
            "审核时间": None,
            "Wiki路径": None,
            "Wiki状态": "review_pending",
            "运行状态": "候选待审",
        },
    )
    state["review_notification"] = _send_notification(
        config,
        record_id=record_id,
        state=state,
        metadata=metadata,
        body=body,
        fields=fields,
        root=root,
        _lark_fn=_lark,
    )
    atomic_write_json(state_path, state)
    return state
