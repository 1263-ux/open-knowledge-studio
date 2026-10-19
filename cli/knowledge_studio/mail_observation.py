"""Read-only projections of visible Mail collaboration facts.

These views do not infer task status, presence, or causality from chronology.
Blocker follow-ups are direct, visible ``reply_to`` references, not resolutions.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from knowledge_studio import mail
from knowledge_studio.mail_activity import delivery_records


_FILTERS = {"all", "awaiting", "blocked", "results", "collaboration"}
_RECEIPT_LABELS = {
    "unobserved": "未见呈现回执",
    "presented": "已呈现",
    "acknowledged": "已确认",
    "read": "已读",
}


def _preview(body: str) -> str:
    return " ".join(str(body or "").split())[:180]


def _query_match(messages: list[dict[str, Any]], query: str) -> dict[str, str] | None:
    """Locate an actual visible message and show the text around its match."""
    for row in reversed(messages):
        meta = row["meta"]
        participants = " ".join([mail._normalise_agent(str(meta.get("from") or "")), *meta.get("to", [])])
        for text in (str(row.get("body") or ""), str(row.get("title") or ""), participants):
            folded = text.casefold()
            index = folded.find(query)
            if index < 0:
                continue
            if len(folded) != len(text):
                # Case folding can expand Unicode characters, e.g. ß -> ss.
                # Convert the match offset back before slicing original text.
                offset = 0
                for original_index, character in enumerate(text):
                    if offset + len(character.casefold()) > index:
                        index = original_index
                        break
                    offset += len(character.casefold())
            start = max(0, index - 60)
            return {"message_id": str(meta["message_id"]), "preview": _preview(text[start:])}
    return None


def _recipient_fact(record: dict[str, Any]) -> dict[str, Any]:
    sessions = [dict(session) for session in record.get("sessions", [])]
    presented_at = max((str(s.get("delivered_at") or "") for s in sessions), default="") or None
    acknowledged_at = max((str(s.get("acknowledged_at") or "") for s in sessions), default="") or None
    state = "unobserved"
    if acknowledged_at:
        state = "acknowledged"
    elif record.get("read_at"):
        state = "read"
    elif presented_at:
        state = "presented"
    return {
        "agent_id": record["agent_id"],
        "state": state,
        "label": _RECEIPT_LABELS[state],
        "presented_at": presented_at,
        "acknowledged_at": acknowledged_at,
        "read_at": record.get("read_at"),
        "sessions": sessions,
    }


def _observation(rows: list[dict[str, Any]], deliveries: dict[str, Any]) -> dict[str, Any]:
    rows = sorted(rows, key=mail._message_sort_key)
    by_id = {str(row["meta"]["message_id"]): row for row in rows}
    links = []
    replies: dict[str, list[str]] = {}
    handoffs = []
    blockers = []
    for row in rows:
        meta = row["meta"]
        mid = str(meta["message_id"])
        reply_to = str(meta.get("reply_to") or "")
        if mail.visible_reply_parent(row, by_id):
            links.append({"from_message_id": reply_to, "to_message_id": mid, "kind": "reply"})
            replies.setdefault(reply_to, []).append(mid)
        base = {
            "message_id": mid,
            "from": mail._normalise_agent(str(meta.get("from") or "")),
            "timestamp": str(meta.get("timestamp") or ""),
        }
        if meta.get("record_kind") == "handoff":
            handoffs.append({
                **base,
                "to": list(meta.get("to", [])),
                "recipients": [_recipient_fact(record) for record in deliveries.get(mid, [])],
            })
        elif meta.get("record_kind") == "blocked":
            blockers.append({**base, "summary": _preview(row.get("body", ""))})
    for handoff in handoffs:
        for recipient in handoff["recipients"]:
            recipient["reply_message_ids"] = [
                mid for mid in replies.get(handoff["message_id"], [])
                if mail._normalise_agent(str(by_id[mid]["meta"].get("from") or "")) == recipient["agent_id"]
            ]
    for blocker in blockers:
        blocker["follow_up_message_ids"] = replies.get(blocker["message_id"], [])
    return {
        "handoffs": handoffs,
        "blockers": blockers,
        "links": links,
        "scope": {"label": "仅展示当前视角可见的消息，未显示的历史不推断"},
    }


def thread_observation(root: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Project only the already viewer-filtered rows supplied by the caller."""
    rows = list(rows)
    return _observation(rows, delivery_records(Path(root), rows))


def _cursor_context(root: Path, viewer: str, filter_kind: str, query: str) -> str:
    data = json.dumps([str(root.resolve()), viewer, filter_kind, query], ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _decode_cursor(cursor: str, context: str) -> tuple[tuple[str, str], tuple[str, str]]:
    try:
        if not isinstance(cursor, str) or len(cursor) > 4096:
            raise ValueError
        raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        value = json.loads(raw)
        if (not isinstance(value, list) or len(value) != 6 or value[0] != 2
                or value[1] != context or not all(isinstance(v, str) for v in value[1:])
                or not value[3] or not value[5]):
            raise ValueError
        return (value[2], value[3]), (value[4], value[5])
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        raise ValueError("invalid overview cursor for this view") from exc


def _encode_cursor(context: str, item: dict[str, Any], cutoff: tuple[str, str]) -> str:
    raw = json.dumps([2, context, item["last_at"], item["thread_id"], *cutoff], ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def overview_data(
    root: Path,
    agent_id: str = "human",
    *,
    filter_kind: str = "all",
    query: str = "",
    limit: int = 50,
    cursor: str = "",
) -> dict[str, Any]:
    """Search all visible history and page Threads by their latest visible fact.

    Cursor anchors are tied to this root/viewer/filter/query and use descending
    (last timestamp, Thread ID) order. A first-page message watermark prevents
    newer messages from moving unseen Threads past the anchor. Receipts remain
    current. Backdated imports, edits, and deletions can still change results;
    this is a bounded live view, not a frozen export.
    ``blocked`` means a historical report exists; a reply never resolves it.
    ``awaiting`` means any visible handoff has a recipient without receipt/read
    evidence, including historical handoffs; it does not create a task state.
    """
    if filter_kind not in _FILTERS:
        raise ValueError("filter must be one of: all, awaiting, blocked, results, collaboration")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    limit = min(limit, 100)
    root = Path(root)
    viewer = mail._normalise_agent(str(agent_id or "human"))
    query = str(query or "").strip().casefold()
    context = _cursor_context(root, viewer, filter_kind, query)
    rows = list(mail.iter_messages(root, viewer))
    if cursor:
        anchor, cutoff = _decode_cursor(cursor, context)
        rows = [row for row in rows if mail._message_sort_key(row) <= cutoff]
    else:
        anchor = None
        cutoff = max((mail._message_sort_key(row) for row in rows), default=("", ""))
    deliveries = delivery_records(root, rows)
    grouped = mail.group_threads(rows)
    counts = {"threads": len(grouped), "awaiting_receipt": 0, "with_blockers": 0, "with_results": 0, "matched": 0}
    items = []
    for thread_id, messages in grouped.items():
        messages.sort(key=mail._message_sort_key)
        observation = _observation(messages, deliveries)
        participants = sorted({
            person
            for row in messages
            for person in [mail._normalise_agent(str(row["meta"].get("from") or "")), *row["meta"].get("to", [])]
            if person and person != "@all"
        })
        awaiting = any(recipient["state"] == "unobserved"
                       for handoff in observation["handoffs"] for recipient in handoff["recipients"])
        blocked = bool(observation["blockers"])
        results = any(row["meta"].get("record_kind") == "result" for row in messages)
        record_kinds = sorted({str(row["meta"].get("record_kind") or "message") for row in messages})
        collaboration = bool(set(record_kinds) & {"goal", "handoff", "blocked", "result", "review_request", "acknowledgement"})
        counts["awaiting_receipt"] += awaiting
        counts["with_blockers"] += blocked
        counts["with_results"] += results
        if not {"all": True, "awaiting": awaiting, "blocked": blocked, "results": results, "collaboration": collaboration}[filter_kind]:
            continue
        match = _query_match(messages, query) if query else None
        if query and match is None:
            continue
        latest = messages[-1]
        meta = latest["meta"]
        evidence = {json.dumps(ref, ensure_ascii=False, sort_keys=True)
                    for row in messages for ref in row["meta"].get("evidence_refs", [])}
        items.append({
            "thread_id": thread_id,
            "title": messages[0].get("title") or "未命名对话",
            "participants": participants,
            "last_at": str(meta.get("timestamp") or ""),
            "message_count": len(messages),
            "record_kinds": record_kinds,
            "latest": {
                "message_id": str(meta["message_id"]),
                "record_kind": str(meta.get("record_kind") or "message"),
                "from": mail._normalise_agent(str(meta.get("from") or "")),
                "timestamp": str(meta.get("timestamp") or ""),
                "preview": _preview(latest.get("body", "")),
                "title": latest.get("title") or "",
            },
            "handoff": observation["handoffs"][-1] if observation["handoffs"] else None,
            "blockers": {
                "total": len(observation["blockers"]),
                "with_follow_up": sum(bool(b["follow_up_message_ids"]) for b in observation["blockers"]),
            },
            "evidence_count": len(evidence),
            **({"match": match} if match is not None else {}),
        })
    counts["matched"] = len(items)
    items.sort(key=lambda item: (item["last_at"], item["thread_id"]), reverse=True)
    if anchor is not None:
        items = [item for item in items if (item["last_at"], item["thread_id"]) < anchor]
    has_more = len(items) > limit
    page = items[:limit]
    return {
        "schema": "mail.overview.v1",
        "scope": {
            "viewer": viewer,
            "label": f"仅包含当前 {viewer.lstrip('@')} 可见的协作记录",
            "coverage": "all_visible_history",
            "message_cutoff": {"timestamp": cutoff[0], "message_id": cutoff[1]} if cutoff[1] else None,
            "pagination_note": "翻页使用首屏消息时间边界，回执读取当前记录；回填旧时间记录、修改或删除仍可能改变结果，请刷新后重查。",
        },
        "counts": counts,
        "items": page,
        "page": {"limit": limit, "next_cursor": _encode_cursor(context, page[-1], cutoff) if has_more else "", "has_more": has_more},
        "partial": False,
    }
