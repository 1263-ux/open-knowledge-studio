"""Feishu Base source adapter for the Open Knowledge Studio Raw pipeline.

This worker owns orchestration only: it reads capture rows, calls the connector
for safe URL probing, delegates extraction to existing Studio adapters, and
writes honest lifecycle state back to Base. It does not bypass authentication,
CAPTCHAs, robots controls, or platform restrictions.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any
import uuid

import yaml

from feishu_worker.config import (
    WorkerConfig,
    configured_knowledge_root as _config_configured_knowledge_root,
    load_config as _config_load_config,
    resolve_lark_cli,
)
from feishu_worker.io_utils import (
    HOME,
    attachment_capability,
    atomic_write_json,
    atomic_write_text,
    content_type_extension,
    _redact_error_text,
    scalar_cell,
    sha256_file,
    utc_now,
)
from feishu_worker.base_client import (
    RETRYABLE_CODES,
    _FATAL_LARK_CODES,
    _LARK_BASE_DELAY,
    _LARK_MAX_RETRIES,
    _LARK_SUBPROCESS_TIMEOUT,
    _extract_lark_error_code,
    _is_fatal_lark_error,
    _is_retryable_lark_error,
    parse_json_output,
    _parse_record_rows,
    lark_json as _base_client_lark_json,
    base_args as _base_client_base_args,
    update_record as _base_client_update_record,
    create_record as _base_client_create_record,
    list_records as _base_client_list_records,
    get_record as _base_client_get_record,
    list_review_records as _base_client_list_review_records,
)
from feishu_worker.claim import (
    parse_base_datetime,
    is_candidate,
    local_claim_lock as _claim_local_claim_lock,
    claim_next_record as _claim_claim_next_record,
    claim_record as _claim_claim_record,
    release_lease as _claim_release_lease,
)

# ── Legacy wrappers: supply ROOT so callers keep one-argument API ──


def load_config(args: argparse.Namespace) -> WorkerConfig:
    return _config_load_config(args, root=ROOT)


def configured_knowledge_root(config: WorkerConfig) -> Path:
    return _config_configured_knowledge_root(config, root=ROOT)


ROOT = Path(__file__).resolve().parents[1]
URL_RE = re.compile(r"https?://[^\s<>\]\[)]+", re.IGNORECASE)
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
CAPTURE_FIELDS = [
    "内容",
    "思考",
    "希望解决的问题",
    "附件",
    "运行状态",
    "运行ID",
    "来源哈希",
    "重试",
    "租约所有者",
    "租约到期",
]
REVIEW_ACTIONS = {"accept", "edit", "reject", "defer"}
REVIEW_ACTION_RE = re.compile(
    r"(?<![A-Za-z])(accept|edit|reject|defer)(?![A-Za-z])",
    re.IGNORECASE,
)


# ── Backward-compatible wrappers (supply ROOT / default projections) ──


def lark_json(config: WorkerConfig, *arguments: str) -> dict[str, Any]:
    return _base_client_lark_json(config, *arguments, root=ROOT)


def base_args(config: WorkerConfig) -> list[str]:
    return _base_client_base_args(config)


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


def create_record(config: WorkerConfig, fields: dict[str, Any]) -> dict[str, Any]:
    """Create one Base record via the worker's monkeypatchable lark_json."""
    return lark_json(
        config,
        "base",
        "+record-upsert",
        *_base_client_base_args(config),
        "--json",
        json.dumps(fields, ensure_ascii=False, separators=(",", ":")),
    )


def list_records(config: WorkerConfig, limit: int = 100) -> list[dict[str, Any]]:
    """Fetch capture-field records via the worker's monkeypatchable lark_json."""
    command = [
        "base",
        "+record-list",
        *_base_client_base_args(config),
        "--limit",
        str(limit),
        "--format",
        "json",
    ]
    for field in CAPTURE_FIELDS:
        command.extend(["--field-id", field])
    command.extend([
        "--filter-json",
        '{"logic":"and","conditions":[["运行状态","intersects",["待处理"]]]}',
    ])
    envelope = lark_json(config, *command)
    data = envelope.get("data", {})
    return _parse_record_rows(
        data.get("data", []),
        data.get("fields", CAPTURE_FIELDS),
        data.get("record_id_list", []),
    )


def get_record(
    config: WorkerConfig,
    record_id: str,
    projection: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch one Base record by id via the worker's monkeypatchable lark_json."""
    fields_requested = projection if projection is not None else CANDIDATE_FIELDS
    command = [
        "base",
        "+record-get",
        *_base_client_base_args(config),
        "--record-id",
        record_id,
        "--format",
        "json",
    ]
    for field in fields_requested:
        command.extend(["--field-id", field])
    envelope = lark_json(config, *command)
    data = envelope.get("data", {})
    rows = data.get("data", [])
    fields = data.get("fields", fields_requested)
    record_ids = data.get("record_id_list", [])
    if not rows:
        raise RuntimeError(f"Base record not found: {record_id}")
    row = rows[0]
    if isinstance(row, list):
        values = dict(zip(fields, row))
    elif isinstance(row, dict):
        values = row.get("fields", row)
    else:
        raise RuntimeError(f"Base record has unsupported shape: {record_id}")
    resolved_id = record_ids[0] if record_ids else record_id
    return {"record_id": resolved_id, "fields": values}


def list_review_records(config: WorkerConfig, limit: int = 100) -> list[dict[str, Any]]:
    """Fetch review-candidate records via the worker's monkeypatchable lark_json."""
    command = [
        "base",
        "+record-list",
        *_base_client_base_args(config),
        "--limit",
        str(limit),
        "--format",
        "json",
    ]
    for field in CANDIDATE_FIELDS:
        command.extend(["--field-id", field])
    envelope = lark_json(config, *command)
    data = envelope.get("data", {})
    return _parse_record_rows(
        data.get("data", []),
        data.get("fields", CANDIDATE_FIELDS),
        data.get("record_id_list", []),
    )


def _connector_binary() -> str:
    """Return the oks-connector CLI path.

    Prefers the entry point next to the current Python (pipx venv).
    Falls back to the source script in dev mode.
    """
    suffix = ".exe" if os.name == "nt" else ""
    injected = Path(sys.executable).parent / f"oks-connector{suffix}"
    if injected.is_file():
        return str(injected)
    script = ROOT / "scripts" / "raw_bundle_adapter.py"
    if script.is_file():
        return str(script)
    raise RuntimeError("oks-connector not found; reinstall open-knowledge-studio")


# ── Claim-layer re-exports ──────────────────────────────────────────────────
# parse_base_datetime and is_candidate are pure functions imported directly
# from feishu_worker.claim — no wrapper needed.  The remaining claim functions
# have legacy wrappers that supply ROOT and inject monkeypatch-compatible
# callables (list_records, get_record, update_record, local_claim_lock).


@contextmanager
def local_claim_lock(config: WorkerConfig):
    """Acquire an exclusive file-based lease lock for the Base+table pair."""
    with _claim_local_claim_lock(config, root=ROOT):
        yield


def claim_next_record(config: WorkerConfig, limit: int = 100) -> tuple[dict[str, Any], str, str] | None:
    """Claim the first candidate record from the pending-rows list."""
    return _claim_claim_next_record(
        config,
        limit=limit,
        _list_fn=list_records,
        _update_fn=update_record,
        _lock_fn=local_claim_lock,
    )


def claim_record(config: WorkerConfig, record_id: str) -> tuple[dict[str, Any], str, str] | None:
    """Claim one explicitly selected Base record without touching other pending rows."""
    return _claim_claim_record(
        config,
        record_id,
        _get_fn=get_record,
        _update_fn=update_record,
        _lock_fn=local_claim_lock,
    )


def release_lease(config: WorkerConfig, record_id: str) -> None:
    """Release the lease on *record_id* by clearing owner and expiry fields."""
    _claim_release_lease(config, record_id, _update_fn=update_record)


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


def candidate_state_path(record_id: str) -> Path:
    safe_record_id = re.sub(r"[^A-Za-z0-9_-]+", "-", record_id).strip("-")
    if not safe_record_id:
        raise ValueError("record_id cannot form a Candidate state path")
    return ROOT / ".oks" / "candidates" / f"{safe_record_id}.json"


def load_candidate_state(record_id: str) -> dict[str, Any]:
    path = candidate_state_path(record_id)
    if not path.is_file():
        raise FileNotFoundError(f"Candidate state not found for Base record: {record_id}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Candidate state is not an object: {path}")
    return value


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
            summary += "…"
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
    try:
        envelope = lark_json(
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


def parse_review_reply(content: str) -> tuple[str, str]:
    """Extract one explicit review action and preserve the user's explanation."""
    text = str(content or "").strip()
    matches = list(REVIEW_ACTION_RE.finditer(text))
    actions = {match.group(1).lower() for match in matches}
    if not matches:
        raise ValueError("review reply must contain accept, edit, reject, or defer")
    if len(actions) != 1:
        raise ValueError("review reply contains conflicting actions")
    action = next(iter(actions))
    pieces: list[str] = []
    cursor = 0
    for match in matches:
        pieces.append(text[cursor:match.start()])
        cursor = match.end()
    pieces.append(text[cursor:])
    comment = " ".join(piece.strip() for piece in pieces if piece.strip())
    comment = comment.strip("`*_# \\t\\r\\n:：,，;；。.!！?-—")
    return action, comment


def event_reviewed_at(value: object) -> str:
    try:
        milliseconds = int(str(value))
    except (TypeError, ValueError):
        return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    return datetime.fromtimestamp(milliseconds / 1000, timezone.utc).astimezone().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def find_candidate_state_for_reply(
    event: dict[str, Any],
) -> tuple[Path, dict[str, Any]] | None:
    parent_ids = {
        str(value)
        for value in (event.get("reply_to"), event.get("root_id"))
        if str(value or "").strip()
    }
    if not parent_ids:
        return None
    state_dir = ROOT / ".oks" / "candidates"
    for path in sorted(state_dir.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            continue
        notification = value.get("review_notification")
        if not isinstance(notification, dict) or notification.get("status") != "sent":
            continue
        if str(notification.get("message_id") or "") not in parent_ids:
            continue
        expected_sender = str(notification.get("recipient") or "")
        if expected_sender and str(event.get("sender_id") or "") != expected_sender:
            continue
        expected_chat = str(notification.get("chat_id") or "")
        if expected_chat and str(event.get("chat_id") or "") != expected_chat:
            continue
        return path, value
    return None


def record_review_event(
    path: Path,
    state: dict[str, Any],
    event: dict[str, Any],
    *,
    action: str,
    comment: str,
) -> None:
    receipts = state.get("review_reply_events")
    if not isinstance(receipts, list):
        receipts = []
    receipts.append(
        {
            "message_id": str(event.get("message_id") or event.get("id") or ""),
            "event_id": str(event.get("event_id") or ""),
            "sender_id": str(event.get("sender_id") or ""),
            "reply_to": str(event.get("reply_to") or ""),
            "root_id": str(event.get("root_id") or ""),
            "action": action,
            "comment": comment,
            "correlation_method": str(event.get("correlation_method") or "reply_context"),
            "received_at": event_reviewed_at(event.get("create_time")),
        }
    )
    state["review_reply_events"] = receipts
    atomic_write_json(path, state)


def read_review_record_after_write(
    config: WorkerConfig,
    record_id: str,
    expected_action: str,
) -> dict[str, Any]:
    record = get_record(config, record_id)
    for delay in (0.25, 0.5, 1.0):
        if scalar_cell(record["fields"].get("审核动作")) == expected_action:
            return record
        time.sleep(delay)
        record = get_record(config, record_id)
    return record


def apply_review_reply_event(
    config: WorkerConfig,
    event: dict[str, Any],
) -> dict[str, Any]:
    """Apply one direct reply to the exact Candidate notification it references."""
    message_id = str(event.get("message_id") or event.get("id") or "").strip()
    if not message_id:
        return {"processed": False, "reason": "missing_message_id"}
    if event.get("chat_type") != "p2p" or event.get("sender_type") != "user":
        return {"processed": False, "reason": "not_personal_user_message", "message_id": message_id}
    if event.get("message_type") not in {"text", "post"}:
        return {"processed": False, "reason": "unsupported_message_type", "message_id": message_id}
    resolved = find_candidate_state_for_reply(event)
    if resolved is None:
        return {"processed": False, "reason": "unknown_review_notification", "message_id": message_id}
    state_path, state = resolved
    receipts = state.get("review_reply_events")
    if isinstance(receipts, list) and any(
        str(item.get("message_id") or "") == message_id
        for item in receipts
        if isinstance(item, dict)
    ):
        return {
            "processed": False,
            "reason": "review_message_already_processed",
            "message_id": message_id,
            "record_id": state.get("record_id"),
        }
    try:
        action, comment = parse_review_reply(str(event.get("content") or ""))
    except ValueError as error:
        return {
            "processed": False,
            "reason": "invalid_review_reply",
            "message_id": message_id,
            "record_id": state.get("record_id"),
            "error": str(error),
        }
    if action in {"edit", "reject"} and not comment:
        return {
            "processed": False,
            "reason": "review_comment_required",
            "message_id": message_id,
            "record_id": state.get("record_id"),
            "action": action,
        }
    record_id = str(state.get("record_id") or "").strip()
    if not record_id:
        raise RuntimeError(f"Candidate state has no record_id: {state_path}")
    patch = {
        "审核动作": action,
        "审核意见": comment or None,
        "修改类型": ["无修改"] if action == "accept" else None,
        "审核时间": event_reviewed_at(event.get("create_time")),
    }
    update_record(config, record_id, patch)
    record = read_review_record_after_write(config, record_id, action)
    review_result = review_candidate(config, record)
    if review_result.get("reason") == "no_review_action":
        raise RuntimeError(
            f"Base did not expose review action {action!r} after a bounded write-read retry"
        )
    latest = load_candidate_state(record_id)
    record_review_event(state_path, latest, event, action=action, comment=comment)
    return {
        "processed": bool(review_result.get("processed")),
        "message_id": message_id,
        "record_id": record_id,
        "candidate_id": state.get("candidate_id"),
        "revision": state.get("revision"),
        "action": action,
        "review": review_result,
    }


def raw_message(config: WorkerConfig, message_id: str) -> dict[str, Any]:
    envelope = lark_json(
        config,
        "api",
        "GET",
        f"/open-apis/im/v1/messages/{message_id}",
        "--as",
        "bot",
        "--format",
        "json",
    )
    data = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
    items = data.get("items") if isinstance(data.get("items"), list) else []
    if len(items) != 1 or not isinstance(items[0], dict):
        raise RuntimeError(f"Feishu message detail is unavailable: {message_id}")
    return items[0]


def decoded_raw_message_content(message: dict[str, Any]) -> str:
    body = message.get("body") if isinstance(message.get("body"), dict) else {}
    raw = body.get("content")
    if not isinstance(raw, str):
        return ""
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(value, dict):
        return str(value.get("text") or value.get("content") or "")
    return str(value)


def pending_review_states_in_chat(chat_id: str) -> list[tuple[Path, dict[str, Any]]]:
    states: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted((ROOT / ".oks" / "candidates").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("last_review_action") in {"accept", "reject"}:
            continue
        notification = value.get("review_notification")
        if not isinstance(notification, dict) or notification.get("status") != "sent":
            continue
        if str(notification.get("chat_id") or "") == chat_id:
            states.append((path, value))
    return states


def review_states_for_prompt(
    chat_id: str,
    prompt_message_id: str,
) -> list[tuple[Path, dict[str, Any]]]:
    states: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted((ROOT / ".oks" / "candidates").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            continue
        notification = value.get("review_notification")
        if not isinstance(notification, dict) or notification.get("status") != "sent":
            continue
        if str(notification.get("chat_id") or "") != chat_id:
            continue
        if str(notification.get("message_id") or "") == prompt_message_id:
            states.append((path, value))
    return states


def reconcile_historical_review_reply(
    config: WorkerConfig,
    *,
    prompt_message_id: str,
    reply_message_id: str,
) -> dict[str, Any]:
    """Recover a missed P2P review event without pretending chronology is a native reply link."""
    prompt = raw_message(config, prompt_message_id)
    reply = raw_message(config, reply_message_id)
    chat_id = str(prompt.get("chat_id") or "")
    if not chat_id or str(reply.get("chat_id") or "") != chat_id:
        raise RuntimeError("Review prompt and reply are not in the same chat")
    reply_id = str(reply.get("message_id") or reply_message_id)
    prompt_states = review_states_for_prompt(chat_id, prompt_message_id)
    if len(prompt_states) == 1:
        _prompt_path, prompt_state = prompt_states[0]
        receipts = prompt_state.get("review_reply_events")
        if isinstance(receipts, list):
            prior = next(
                (
                    item
                    for item in receipts
                    if isinstance(item, dict) and str(item.get("message_id") or "") == reply_id
                ),
                None,
            )
            if prior is not None:
                return {
                    "processed": False,
                    "reason": "review_message_already_processed",
                    "message_id": reply_id,
                    "record_id": prompt_state.get("record_id"),
                    "correlation_method": str(
                        prior.get("correlation_method") or "reply_context"
                    ),
                }
    pending = pending_review_states_in_chat(chat_id)
    matching = [
        (path, state)
        for path, state in pending
        if str(state.get("review_notification", {}).get("message_id") or "") == prompt_message_id
    ]
    if len(pending) != 1 or len(matching) != 1:
        raise RuntimeError("Historical review fallback requires exactly one pending Candidate in the chat")
    _state_path, state = matching[0]
    notification = state["review_notification"]
    sender = reply.get("sender") if isinstance(reply.get("sender"), dict) else {}
    if sender.get("sender_type") != "user" or str(sender.get("id") or "") != str(
        notification.get("recipient") or ""
    ):
        raise RuntimeError("Historical review reply sender does not match the configured reviewer")
    parent_id = str(reply.get("parent_id") or "")
    root_id = str(reply.get("root_id") or "")
    if prompt_message_id in {parent_id, root_id}:
        method = "native_reply_context"
    else:
        try:
            prompt_position = int(str(prompt.get("message_position")))
            reply_position = int(str(reply.get("message_position")))
        except (TypeError, ValueError) as error:
            raise RuntimeError("Historical review fallback requires message positions") from error
        if reply_position != prompt_position + 1:
            raise RuntimeError("Historical review fallback requires the reply to immediately follow the prompt")
        if int(str(reply.get("create_time") or 0)) <= int(str(prompt.get("create_time") or 0)):
            raise RuntimeError("Historical review reply is not newer than the prompt")
        method = "p2p_sequence_fallback"
    event = {
        "event_id": "",
        "message_id": reply_id,
        "reply_to": prompt_message_id,
        "root_id": root_id,
        "chat_id": chat_id,
        "chat_type": "p2p",
        "sender_id": str(sender.get("id") or ""),
        "sender_type": "user",
        "message_type": str(reply.get("msg_type") or ""),
        "content": decoded_raw_message_content(reply),
        "create_time": str(reply.get("create_time") or ""),
        "correlation_method": method,
    }
    outcome = apply_review_reply_event(config, event)
    outcome["correlation_method"] = method
    return outcome


def apply_review_event_with_fallback(
    config: WorkerConfig,
    event: dict[str, Any],
) -> dict[str, Any]:
    outcome = apply_review_reply_event(config, event)
    if outcome.get("reason") != "unknown_review_notification":
        return outcome
    chat_id = str(event.get("chat_id") or "").strip()
    message_id = str(event.get("message_id") or event.get("id") or "").strip()
    if not chat_id or not message_id:
        return outcome
    pending = pending_review_states_in_chat(chat_id)
    if len(pending) != 1:
        return outcome
    notification = pending[0][1].get("review_notification")
    prompt_message_id = (
        str(notification.get("message_id") or "").strip()
        if isinstance(notification, dict)
        else ""
    )
    if not prompt_message_id:
        return outcome
    try:
        return reconcile_historical_review_reply(
            config,
            prompt_message_id=prompt_message_id,
            reply_message_id=message_id,
        )
    except RuntimeError as error:
        return {**outcome, "fallback_error": str(error)}


def consume_review_events(
    config: WorkerConfig,
    *,
    max_events: int,
    timeout: str,
) -> dict[str, Any]:
    if max_events < 1:
        raise ValueError("max_events must be at least 1")
    jq_filter = 'select(.chat_type=="p2p" and .sender_type=="user")'
    if config.review_recipient_user_id:
        recipient = json.dumps(config.review_recipient_user_id, ensure_ascii=False)
        jq_filter = f"{jq_filter} | select(.sender_id=={recipient})"
    result = subprocess.run(
        [
            str(config.lark_cli),
            "event",
            "consume",
            "im.message.receive_v1",
            "--as",
            "bot",
            "--max-events",
            str(max_events),
            "--timeout",
            timeout,
            "--jq",
            jq_filter,
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Feishu review event consumer failed ({result.returncode}): "
            f"{(result.stderr or result.stdout).strip()}"
        )
    events: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            continue
        events.append(event)
        outcomes.append(apply_review_event_with_fallback(config, event))
    return {
        "events_received": len(events),
        "outcomes": outcomes,
        "consumer_stderr": result.stderr.strip(),
    }


def publish_candidate(
    config: WorkerConfig,
    record_id: str,
    candidate_file: Path,
) -> dict[str, Any]:
    record = get_record(config, record_id, [*CANDIDATE_FIELDS, "内容", "思考"])
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
    knowledge_root = configured_knowledge_root(config)
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

    state_path = candidate_state_path(record_id)
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
            target.relative_to(ROOT).as_posix()
            if knowledge_root == ROOT.resolve()
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
    update_record(
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
    state["review_notification"] = send_candidate_review_notification(
        config,
        record_id=record_id,
        state=state,
        metadata=metadata,
        body=body,
        fields=fields,
    )
    atomic_write_json(state_path, state)
    return state


def promote_candidate_document(
    candidate_path: Path,
    reviewed_body: str,
    review: dict[str, Any],
    *,
    knowledge_root: Path | None = None,
) -> Path:
    metadata, _body = parse_candidate_document(candidate_path.read_text(encoding="utf-8"))
    metadata["status"] = "draft"
    metadata["review"] = review
    atomic_write_text(candidate_path, render_candidate_document(metadata, reviewed_body))
    cli_root = str(ROOT / "cli")
    if cli_root not in sys.path:
        sys.path.insert(0, cli_root)
    from knowledge_studio import store

    previous_root = os.environ.get("OKS_ROOT")
    if knowledge_root is not None:
        os.environ["OKS_ROOT"] = str(knowledge_root)
    try:
        promoted_slug = store.promote_draft(
            candidate_path.stem,
            slug_hint=candidate_path.stem,
        )
        page = store.get_wiki_page(promoted_slug)
    finally:
        if previous_root is None:
            os.environ.pop("OKS_ROOT", None)
        else:
            os.environ["OKS_ROOT"] = previous_root
    if not page or not page.get("file_path"):
        raise RuntimeError(f"Promoted Wiki page cannot be resolved: {promoted_slug}")
    return Path(page["file_path"]).resolve()


def review_candidate(config: WorkerConfig, record: dict[str, Any]) -> dict[str, Any]:
    record_id = record["record_id"]
    fields = record["fields"]
    action = scalar_cell(fields.get("审核动作"))
    if action not in REVIEW_ACTIONS:
        return {"processed": False, "reason": "no_review_action", "record_id": record_id}
    state = load_candidate_state(record_id)
    if scalar_cell(fields.get("候选ID")) != state.get("candidate_id"):
        raise RuntimeError(f"Candidate ID does not match local state for {record_id}")
    fingerprint = candidate_review_fingerprint(fields)
    if state.get("last_review_fingerprint") == fingerprint:
        return {"processed": False, "reason": "review_already_processed", "record_id": record_id}
    knowledge_root = configured_knowledge_root(config)
    stored_candidate = Path(str(state["candidate_path"]))
    candidate_path = (
        stored_candidate.resolve()
        if stored_candidate.is_absolute()
        else (ROOT / stored_candidate).resolve()
    )
    if knowledge_root not in candidate_path.parents or not candidate_path.is_file():
        raise RuntimeError(
            f"Candidate file is unavailable or outside the configured knowledge root: {candidate_path}"
        )

    reviewed_at = scalar_cell(fields.get("审核时间")) or datetime.now(timezone.utc).astimezone().strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    comment = str(fields.get("审核意见") or "").strip()
    change_types = fields.get("修改类型") if isinstance(fields.get("修改类型"), list) else []
    if action in {"edit", "reject"} and not comment:
        raise RuntimeError(f"Review action {action} requires 审核意见")
    history_item = {
        "action": action,
        "comment": comment,
        "change_types": change_types,
        "reviewed_at": reviewed_at,
        "candidate_sha256": hashlib.sha256(
            str(fields.get("候选内容") or "").encode("utf-8")
        ).hexdigest(),
    }
    patch: dict[str, Any]
    wiki_path: Path | None = None
    if action == "accept":
        reviewed_body = str(fields.get("候选内容") or "").strip()
        if len(reviewed_body) < 50:
            raise RuntimeError("Accepted Candidate content is empty or too short")
        wiki_path = promote_candidate_document(
            candidate_path,
            reviewed_body,
            {
                "outcome": "success",
                "decision_correct": True,
                "lesson": comment,
                "reviewed_at": str(reviewed_at),
            },
            knowledge_root=knowledge_root,
        )
        patch = {
            "运行状态": "已晋升",
            "Wiki状态": "promoted",
            "Wiki路径": wiki_path.relative_to(knowledge_root).as_posix(),
        }
    elif action == "reject":
        metadata, body = parse_candidate_document(candidate_path.read_text(encoding="utf-8"))
        metadata["status"] = "rejected"
        metadata["review"] = {
            "outcome": "failure",
            "decision_correct": False,
            "lesson": comment,
            "reviewed_at": str(reviewed_at),
        }
        atomic_write_text(candidate_path, render_candidate_document(metadata, body))
        patch = {"运行状态": "已拒绝", "Wiki状态": "rejected", "Wiki路径": None}
    elif action == "edit":
        patch = {"运行状态": "需人工", "Wiki状态": "candidate", "Wiki路径": None}
    else:
        patch = {"运行状态": "候选待审", "Wiki状态": "review_pending", "Wiki路径": None}
    patch["审核时间"] = str(reviewed_at)

    history = state.get("review_history", [])
    if not isinstance(history, list):
        history = []
    history.append(history_item)
    state["review_history"] = history
    state["last_review_fingerprint"] = fingerprint
    state["last_review_action"] = action
    state["last_reviewed_at"] = reviewed_at
    if wiki_path is not None:
        state["wiki_path"] = wiki_path.relative_to(knowledge_root).as_posix()
    atomic_write_json(candidate_state_path(record_id), state)
    update_record(config, record_id, patch)
    return {"processed": True, "record_id": record_id, "action": action, "patch": patch}


def process_next_review(config: WorkerConfig, limit: int = 100) -> dict[str, Any]:
    for record in list_review_records(config, limit):
        fields = record["fields"]
        action = scalar_cell(fields.get("审核动作"))
        status = scalar_cell(fields.get("运行状态"))
        if action not in REVIEW_ACTIONS or status in {"已晋升", "已拒绝"}:
            continue
        result = review_candidate(config, record)
        if result.get("processed"):
            return result
    return {"processed": False, "reason": "no_pending_reviews"}


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


def capture_user_note(fields: dict[str, Any]) -> str | None:
    thought = str(fields.get("思考") or "").strip()
    question = str(fields.get("希望解决的问题") or "").strip()
    parts = []
    if thought:
        parts.append(thought)
    if question:
        parts.append(f"希望解决的问题：{question}")
    return "\n\n".join(parts) or None


def capture_content_hash(fields: dict[str, Any]) -> str:
    canonical = {
        "source_type": "feishu_base",
        "source_uri": extract_url(fields.get("内容")),
        "content": fields.get("内容"),
        "user_note": capture_user_note(fields),
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
        "user_note": capture_user_note(fields),
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
    connector = _connector_binary()
    result = subprocess.run(
        [connector, "probe", url],
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
            connector,
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


def package_local_attachment(config: WorkerConfig, source: Path, output: Path) -> dict[str, Any]:
    if output.is_dir():
        validation = subprocess.run(
            [_connector_binary(), "validate", str(output)],
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
            _connector_binary(),
            "ingest",
            str(source),
            "--output",
            str(output),
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
        [_connector_binary(), "validate", str(output)],
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


def package_routed_source(config: WorkerConfig, source: str, output: Path) -> dict[str, Any]:
    if output.is_dir():
        validation = subprocess.run(
            [_connector_binary(), "validate", str(output)],
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
        raise RuntimeError(f"existing routed output is invalid: {json.dumps(report, ensure_ascii=False)}")
    result = subprocess.run(
        [
            _connector_binary(),
            "ingest",
            source,
            "--output",
            str(output),
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
        [_connector_binary(), "validate", str(output)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    report = parse_json_output(validation)
    if report.get("valid") is not True:
        raise RuntimeError(f"routed Raw validation failed: {json.dumps(report, ensure_ascii=False)}")
    return report


def package_public_web(
    config: WorkerConfig,
    url: str,
    output: Path,
    human_context: str,
) -> dict[str, Any]:
    from extractors.web import package_web

    try:
        package_web(
            url,
            output,
            human_context=human_context or "omitted",
        )
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc
    validation = subprocess.run(
        [_connector_binary(), "validate", str(output)],
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
    connector = _connector_binary()
    command = [
            connector,
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

    run_id = f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
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
                "错误说明": _redact_error_text(failure["message"])[:500],
                "质量状态": "failed",
                "Raw Bundle": None,
            },
        )
        return run


def process_record(
    config: WorkerConfig,
    record: dict[str, Any],
    *,
    claimed_run_id: str | None = None,
) -> dict[str, Any]:
    record_id = record["record_id"]
    fields = record["fields"]
    url = extract_url(fields.get("内容"))
    attachment_descriptors = normalize_attachments(fields.get("附件"))
    run_id = claimed_run_id or f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
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
                    "错误说明": _redact_error_text(failure["message"])[:500],
                    "质量状态": "failed",
                    "Raw Bundle": None,
                    "总结": f"附件未生成 Raw：{_redact_error_text(failure['message'])}"[:1000],
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
                "错误说明": _redact_error_text(message)[:500],
                "质量状态": "failed",
                "Raw Bundle": None,
                "总结": f"未生成 Raw：{code}。{_redact_error_text(message)}"[:1000],
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

    if receipt.get("next_action") == "platform_extractor":
        try:
            route = receipt.get("route_plan") or {}
            platform_reference = {
                "schema_version": "oks-platform-source-reference/v0.1",
                "source_url": url,
                "final_url": str(receipt.get("final_url") or url),
                "platform": route.get("platform"),
                "source_type": route.get("source_type"),
                "original_media_retained": False,
                "content_hash_status": "unavailable",
                "retention_note": "The extractor may acquire temporary media; Raw retains captions, frames, OCR and metadata rather than the full platform media file.",
            }
            reference_path = run_dir / "platform-source.json"
            atomic_write_json(reference_path, platform_reference)
            capture["source_snapshot"] = {
                "kind": "reference",
                "content_hash_status": "unavailable",
                "final_url": platform_reference["final_url"],
                "content_type": receipt.get("content_type"),
                "size": reference_path.stat().st_size,
                "sha256": sha256_file(reference_path),
            }
            source_hash = envelope_content_hash(capture)
            capture["content_hash"] = source_hash
            capture["capture_id"] = f"feishu-{record_id}-{source_hash[:12]}"
            run["capture_id"] = capture["capture_id"]
            run["recipe_version"] = "feishu-platform-video-v0.1"
            run["job"]["capability"] = "video.watch"
            run["inputs"] = [{"dataset_id": capture["capture_id"], "uri": capture["source_uri"], "kind": "capture", "sha256": source_hash}]
            run["modalities"]["text"].update({"status": "skipped", "capability": None})
            run["modalities"]["video"].update({"status": "running", "capability": "video.watch"})
            atomic_write_json(run_dir / "capture-envelope.json", capture)
            atomic_write_json(run_dir / "processing-run.json", run)
            update_record(config, record_id, {"运行状态": "探测中", "来源哈希": source_hash, "采集模式": "平台提取器"})
            output = config.output_root / f"feishu-{record_id}-{source_hash[:10]}-platform-video"
            report = package_routed_source(config, url, output)
            metadata_path = output / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["capture_envelope"] = capture
            metadata["fetch_receipt"] = str((run_dir / "fetch-receipt.json").resolve())
            metadata["platform_source_reference"] = str(reference_path.resolve())
            atomic_write_json(metadata_path, metadata)
            quality_path = output / "quality-report.json"
            quality_report = json.loads(quality_path.read_text(encoding="utf-8"))
            quality = report.get("processing_status") or quality_report.get("processing_status") or metadata.get("processing_status") or "partial"
            frame_count = int(quality_report.get("frame_count") or 0)
            transcript_count = int(quality_report.get("transcript_segment_count") or 0)
            ocr_count = int(quality_report.get("ocr_block_count") or 0)
            run["modalities"]["video"].update({"status": "succeeded" if frame_count else "skipped", "evidence_count": frame_count})
            run["modalities"]["asr"].update({"status": "succeeded" if transcript_count else "skipped", "capability": "video.watch" if transcript_count else None, "evidence_count": transcript_count})
            run["modalities"]["ocr"].update({"status": "succeeded" if ocr_count else "skipped", "capability": "image.rapidocr" if ocr_count else None, "evidence_count": ocr_count})
            run["warnings"] = [str(item) for item in quality_report.get("warnings", [])]
            run["outputs"] = [{"dataset_id": f"bundle:{capture['capture_id']}", "uri": str(output), "kind": "bundle", "sha256": None}]
            finish_run(run, "complete" if quality == "complete" else "partial")
            atomic_write_json(run_dir / "processing-run.json", run)
            finalize_raw_v2(config, output, run_dir / "capture-envelope.json", run_dir / "processing-run.json", reference_path)
            update_record(
                config,
                record_id,
                {
                    "运行状态": "Raw就绪",
                    "采集模式": "平台提取器",
                    "Raw Bundle": str(output),
                    "质量状态": quality,
                    "错误码": None,
                    "错误说明": None,
                    "总结": f"平台视频 Raw Bundle v0.2 已生成；帧={frame_count}，字幕/ASR段={transcript_count}，OCR块={ocr_count}；未永久保存整段平台媒体。",
                },
            )
        except Exception as error:
            failure = {"code": "PLATFORM_EXTRACTOR_FAILED", "message": str(error)}
            run["outputs"] = []
            finish_run(run, "failed", disposition="retryable", error=failure, error_modality="video")
            atomic_write_json(run_dir / "processing-run.json", run)
            update_record(
                config,
                record_id,
                {
                    "运行状态": "可重试失败",
                    "采集模式": "平台提取器",
                    "错误码": failure["code"],
                    "错误说明": _redact_error_text(failure["message"])[:500],
                    "质量状态": "failed",
                    "Raw Bundle": None,
                    "总结": f"平台提取器未生成 Raw：{_redact_error_text(failure['message'])}"[:1000],
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
                    "错误说明": _redact_error_text(failure["message"])[:500],
                    "质量状态": "failed",
                    "Raw Bundle": None,
                    "总结": f"公网文件未生成 Raw：{_redact_error_text(failure['message'])}"[:1000],
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
                "错误说明": _redact_error_text(failure["message"])[:500],
                "质量状态": "failed",
                "Raw Bundle": None,
                "总结": f"未生成 Raw：{failure['code']}。{_redact_error_text(failure['message'])}"[:1000],
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
    parser.add_argument("--knowledge-root")
    parser.add_argument("--lease-seconds", type=int, default=3600)
    parser.add_argument("--review-recipient-user-id")
    parser.add_argument(
        "--review-message-identity",
        choices=("bot", "user"),
        default=None,
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    enqueue = subcommands.add_parser("enqueue", help="Create one pending capture row.")
    enqueue.add_argument("content")
    enqueue.add_argument("--thought", default="")
    enqueue.add_argument("--rating", choices=("A", "B", "C"))
    once = subcommands.add_parser("run-once", help="Process at most one pending row.")
    once.add_argument("--limit", type=int, default=100)
    selected = subcommands.add_parser(
        "run-record",
        help="Process one explicitly selected pending Base record.",
    )
    selected.add_argument("--record-id", required=True)
    browser = subcommands.add_parser("complete-browser", help="Complete one JS-rendered record from a controlled browser snapshot.")
    browser.add_argument("--record-id", required=True)
    browser.add_argument("--snapshot-dir", type=Path, required=True)
    publish = subcommands.add_parser(
        "publish-candidate",
        help="Publish an Agent-authored Teach-back Candidate to its Base record.",
    )
    publish.add_argument("--record-id", required=True)
    publish.add_argument("--candidate-file", type=Path, required=True)
    review = subcommands.add_parser(
        "review-once",
        help="Consume at most one new accept/edit/reject/defer action from Base.",
    )
    review.add_argument("--limit", type=int, default=100)
    listen = subcommands.add_parser(
        "listen-reviews",
        help="Consume bounded Feishu personal replies and apply linked Candidate reviews.",
    )
    listen.add_argument("--max-events", type=int, default=1)
    listen.add_argument("--timeout", default="5m")
    reconcile = subcommands.add_parser(
        "reconcile-review",
        help="Recover one missed personal review reply from immutable message IDs.",
    )
    reconcile.add_argument("--prompt-message-id", required=True)
    reconcile.add_argument("--reply-message-id", required=True)
    return parser.parse_args()


def main() -> int:
    # Windows PowerShell commonly exposes a GBK console. Raw extraction output
    # can contain arbitrary Unicode, so a successful run must not fail while
    # serializing its final machine-readable result.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
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
    if args.command == "publish-candidate":
        result = publish_candidate(config, args.record_id, args.candidate_file)
        print(json.dumps({"published": True, "candidate": result}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "review-once":
        result = process_next_review(config, args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "listen-reviews":
        result = consume_review_events(
            config,
            max_events=args.max_events,
            timeout=args.timeout,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "reconcile-review":
        result = reconcile_historical_review_reply(
            config,
            prompt_message_id=args.prompt_message_id,
            reply_message_id=args.reply_message_id,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "run-record":
        claimed = claim_record(config, args.record_id)
    else:
        claimed = claim_next_record(config, args.limit)
    if claimed is None:
        reason = "record_not_claimable" if args.command == "run-record" else "no_pending_records"
        print(json.dumps({"processed": False, "reason": reason}, ensure_ascii=False))
        return 0
    record, run_id, _owner = claimed
    try:
        result = process_record(config, record, claimed_run_id=run_id)
    finally:
        release_lease(config, record["record_id"])
    print(json.dumps({"processed": True, "run": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
