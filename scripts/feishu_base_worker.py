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
from feishu_worker.capture import (
    URL_RE,
    extract_url,
    normalize_attachments,
    capture_user_note,
    capture_content_hash,
    envelope_content_hash,
    capture_envelope,
)
from feishu_worker.source_router import (
    _connector_binary as _source_router__connector_binary,
    package_local_attachment as _source_router_package_local_attachment,
    package_routed_source as _source_router_package_routed_source,
    package_public_web as _source_router_package_public_web,
)
from feishu_worker.pipeline import process_record as _pipeline_process_record
from feishu_worker.candidate import (
    parse_candidate_document as _candidate_parse_candidate_document,
    render_candidate_document as _candidate_render_candidate_document,
    candidate_state_path as _candidate_candidate_state_path,
    load_candidate_state as _candidate_load_candidate_state,
    candidate_review_fingerprint as _candidate_candidate_review_fingerprint,
    render_candidate_review_message as _candidate_render_candidate_review_message,
    send_candidate_review_notification as _candidate_send_candidate_review_notification,
    publish_candidate as _candidate_publish_candidate,
)

# ── Legacy wrappers: supply ROOT so callers keep one-argument API ──


def load_config(args: argparse.Namespace) -> WorkerConfig:
    return _config_load_config(args, root=ROOT)


def configured_knowledge_root(config: WorkerConfig) -> Path:
    return _config_configured_knowledge_root(config, root=ROOT)


ROOT = Path(__file__).resolve().parents[1]
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
    """Return the oks-connector CLI path (delegates to feishu_worker.source_router)."""
    return _source_router__connector_binary(ROOT)


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
    return _candidate_parse_candidate_document(text)


def render_candidate_document(metadata: dict[str, Any], body: str) -> str:
    return _candidate_render_candidate_document(metadata, body)


def candidate_state_path(record_id: str) -> Path:
    return _candidate_candidate_state_path(record_id, root=ROOT)


def load_candidate_state(record_id: str) -> dict[str, Any]:
    return _candidate_load_candidate_state(record_id, root=ROOT)


def candidate_review_fingerprint(fields: dict[str, Any]) -> str:
    return _candidate_candidate_review_fingerprint(fields)


def render_candidate_review_message(
    *,
    record_id: str,
    candidate_id: str,
    revision: int,
    metadata: dict[str, Any],
    body: str,
    fields: dict[str, Any],
) -> str:
    return _candidate_render_candidate_review_message(
        record_id=record_id,
        candidate_id=candidate_id,
        revision=revision,
        metadata=metadata,
        body=body,
        fields=fields,
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
    return _candidate_send_candidate_review_notification(
        config,
        record_id=record_id,
        state=state,
        metadata=metadata,
        body=body,
        fields=fields,
        root=ROOT,
        _lark_fn=lark_json,
    )


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
    return _candidate_publish_candidate(
        config,
        record_id,
        candidate_file,
        root=ROOT,
        _get_fn=get_record,
        _update_fn=update_record,
        _lark_fn=lark_json,
        _send_notification_fn=send_candidate_review_notification,
    )


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
    """Package a local attachment file into a Raw bundle (delegates to feishu_worker.source_router)."""
    return _source_router_package_local_attachment(config, source, output, root=ROOT)


def package_routed_source(config: WorkerConfig, source: str, output: Path) -> dict[str, Any]:
    """Package a platform-routed source into a Raw bundle (delegates to feishu_worker.source_router)."""
    return _source_router_package_routed_source(config, source, output, root=ROOT)


def package_public_web(
    config: WorkerConfig,
    url: str,
    output: Path,
    human_context: str,
) -> dict[str, Any]:
    """Package a public web page into a Raw bundle (delegates to feishu_worker.source_router)."""
    return _source_router_package_public_web(config, url, output, human_context, root=ROOT)


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
    """Process one claimed Base record through the full Raw pipeline (delegates to feishu_worker.pipeline).

    Explicitly passes the worker's own callables so that monkeypatched
    attributes (update_record, probe_source, package_routed_source, etc.)
    remain effective in tests -- the pipeline uses module-level defaults
    only when no callback is supplied.
    """
    return _pipeline_process_record(
        config,
        record,
        claimed_run_id=claimed_run_id,
        _update_record=update_record,
        _download_attachments=download_attachments,
        _package_local_attachment=package_local_attachment,
        _finalize_raw_v2=finalize_raw_v2,
        _probe_source=probe_source,
        _download_public_source=download_public_source,
        _package_routed_source=package_routed_source,
        _package_public_web=package_public_web,
    )


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
