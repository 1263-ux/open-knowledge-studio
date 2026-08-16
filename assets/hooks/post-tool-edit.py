#!/usr/bin/env python3
"""PostToolUse hook — file conflict detection + recall supplement.

Reads JSON payload on stdin (Claude Code / Qoder PostToolUse):
{ tool_name, tool_input, session_id, cwd }.

Two jobs (both fail-open, never block a tool):

1. **File conflict detection** (Edit/Write/MultiEdit only):
   - Append to records/file-edits.jsonl (agent_id + file + ts) — git-shared
   - Check if another agent edited the same file within CONFLICT_WINDOW
   - If conflict, write mail to inbox/ for current agent (type=conflict)

2. **Recall supplement** (any tool — solves long-task blind spot):
   - UserPromptSubmit only fires when the user speaks; a long autonomous task
     (Read → Edit → Bash → Edit → ...) has no new user prompts, so recall
     never injects — the agent executes blind to relevant memory.
   - PostToolUse fires after every tool call: we extract a query from the
     tool operation (file basename / bash command / grep pattern) and run
     recall with a HIGHER floor (0.9) + lower topn (2) to avoid noise.
   - Shares recall-state-{session}.json + cooldown with UserPromptSubmit so
     the same slug isn't re-injected twice.

Tunables via env:
  OKS_CONFLICT_WINDOW  seconds to consider a conflict (default 300 = 5 min)
  OKS_AGENT_ID         agent identity (default: cwd basename)
  OKS_POSTTOOL_FLOOR   min relevance for PostToolUse recall (default 0.9, higher than UserPromptSubmit's 0.7)
  OKS_POSTTOOL_TOPN    max memories injected per PostToolUse (default 2, less than UserPromptSubmit's 3)
  OKS_RECALL_COOLDOWN  shared with UserPromptSubmit (default 10 turns)
  OKS_SEARCH_BACKEND   search backend (default native)
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from _persistence import append_jsonl, atomic_write_text, file_lock

CONFLICT_WINDOW = int(os.environ.get("OKS_CONFLICT_WINDOW", "300"))

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "edit", "write", "multiedit"}


def _load_payload() -> dict:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _kb_root() -> Path | None:
    env = os.environ.get("OKS_ROOT")
    if env and Path(env).is_dir():
        return Path(env)
    try:
        from knowledge_studio.config import get_kb_root
        r = get_kb_root()
        return r if r and Path(r).is_dir() else None
    except Exception:
        pass
    cwd = Path.cwd()
    return cwd if (cwd / "wiki").is_dir() else None


def _agent_id(payload: dict, cwd: str) -> str:
    aid = os.environ.get("OKS_AGENT_ID", "").strip()
    if aid:
        return aid
    aid = str(payload.get("agent_id", "") or "").strip()
    if aid:
        return aid
    if cwd:
        name = Path(cwd).name
        if name:
            return name
    return "unknown"


# ── File conflict detection (unchanged) ──

def _file_edits_path(kb_root: Path) -> Path:
    d = kb_root / "records"
    d.mkdir(parents=True, exist_ok=True)
    return d / "file-edits.jsonl"


def _append_file_edit(kb_root: Path, agent_id: str, file_path: str) -> None:
    path = _file_edits_path(kb_root)
    rec = {
        "agent_id": agent_id,
        "file_path": file_path,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    try:
        append_jsonl(
            path,
            rec,
            lock_path=kb_root / ".oks" / "locks" / "file-edits.lock",
        )
    except Exception:
        pass


def _check_conflict(kb_root: Path, agent_id: str, file_path: str) -> dict | None:
    """Check if another agent edited this file within CONFLICT_WINDOW."""
    path = _file_edits_path(kb_root)
    if not path.is_file():
        return None
    now = datetime.now(timezone.utc)
    window = timedelta(seconds=CONFLICT_WINDOW)
    try:
        lock = kb_root / ".oks" / "locks" / "file-edits.lock"
        with file_lock(lock):
            for line in reversed(path.read_text(encoding="utf-8").splitlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("file_path") != file_path:
                        continue
                    if rec.get("agent_id") == agent_id:
                        continue
                    ts = datetime.fromisoformat(rec.get("ts", ""))
                    if now - ts < window:
                        return rec
                except Exception:
                    continue
    except Exception:
        pass
    return None


def _write_conflict_mail(kb_root: Path, agent_id: str, file_path: str, other: dict) -> None:
    inbox = kb_root / "mail" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    ts = now.strftime("%Y%m%dT%H%M%S")
    slug = f"{ts}-conflict-{agent_id}"
    other_id = other.get("agent_id", "unknown")
    other_ts = str(other.get("ts", "?"))[:19]
    content = (
        "---\n"
        f"from: system\n"
        f"to: @{agent_id}\n"
        f"timestamp: {now.isoformat()}\n"
        "read: false\n"
        "type: conflict\n"
        "priority: urgent\n"
        "action: review\n"
        "---\n\n"
        f"# 文件冲突: {Path(file_path).name}\n\n"
        f"你刚编辑了 `{file_path}`，但 `{other_id}` 在 {other_ts} 也编辑了该文件。\n"
        f"可能冲突——建议 review 对方的改动后再继续。\n"
    )
    try:
        (inbox / f"{slug}.md").write_text(content, encoding="utf-8")
    except Exception:
        pass


# ── Recall supplement (new — long-task blind spot) ──

def _state_path(session_id: str, kb_root: Path) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[:80] or "default"
    d = kb_root / ".oks"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"recall-state-{safe}.json"


def _load_state(path: Path) -> dict:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(state, dict):
            return {"n": int(state.get("n", 0)), "seen": dict(state.get("seen", {}))}
    except Exception:
        pass
    return {"n": 0, "seen": {}}


def _save_state(path: Path, state: dict) -> None:
    try:
        atomic_write_text(path, json.dumps(state))
    except Exception:
        pass


def _inject_trace_path(kb_root: Path) -> Path:
    d = kb_root / "records"
    d.mkdir(parents=True, exist_ok=True)
    return d / "inject.jsonl"


def _append_inject_trace(
    kb_root: Path, agent_id: str, session_id: str, query: str,
    picked: list, source: str = "posttool",
) -> None:
    """Append inject record (git-shared training signal, same format as UserPromptSubmit)."""
    path = _inject_trace_path(kb_root)
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "agent_id": agent_id,
        "session_id": session_id,
        "source": source,
        "query": query,
        "injected": [
            {
                "slug": str(h.get("slug", "")),
                "title": str(h.get("title", "")),
                "relevance": float(h.get("relevance", 0)),
                "type": str(h.get("type", "")),
            }
            for h in picked
        ],
    }
    try:
        append_jsonl(path, rec, lock_path=kb_root / ".oks" / "locks" / "inject.lock")
    except Exception:
        pass


def _query_from_tool(tool_name: str, tool_input: dict) -> str:
    """Extract a recall query from the tool operation.

    Long-task agent has no user prompt — we derive a query from what the
    tool just touched:
      Edit/Write/Read/MultiEdit → file basename (stem, no ext)
      Bash                      → command first ~6 meaningful words
      Grep/Glob                 → pattern
    """
    for k in ("file_path", "path"):
        fp = str(tool_input.get(k, "") or "")
        if fp:
            stem = Path(fp).stem
            if stem:
                return stem
    cmd = str(tool_input.get("command", "") or "")
    if cmd:
        words = [
            w for w in re.split(r"\s+", cmd)
            if w and not w.startswith("-")
            and w not in ("&&", "||", "|", "sudo", "cd", ";", "python", "python3")
        ]
        return " ".join(words[:6])
    pat = str(tool_input.get("pattern", "") or tool_input.get("query", "") or "")
    if pat:
        return pat
    return ""


def _recall_supplement(
    kb_root: Path, session_id: str, query: str, agent_id: str
) -> str:
    """PostToolUse recall — inject relevant memory after tool calls.

    Higher floor (0.9) + lower topn (2) than UserPromptSubmit (0.7 / 3) —
    PostToolUse fires often, we only surface high-confidence hits to avoid
    drowning the agent's execution flow.
    """
    if not query or len(query) < 3:
        return ""
    try:
        from knowledge_studio.recall import recall
    except Exception:
        return ""

    floor = float(os.environ.get("OKS_POSTTOOL_FLOOR", "0.9"))
    topn = int(os.environ.get("OKS_POSTTOOL_TOPN", "2"))
    cooldown = int(os.environ.get("OKS_RECALL_COOLDOWN", "10"))
    search_backend = os.environ.get("OKS_SEARCH_BACKEND", "native")

    state_path = _state_path(session_id, kb_root)
    state = _load_state(state_path)
    state["n"] += 1
    turn = state["n"]

    try:
        hits = recall(
            query=query, limit=max(topn * 3, 6),
            knowledge_only=True, search_backend=search_backend,
        ).get("knowledge", [])
    except Exception:
        hits = []

    picked = []
    for h in hits:
        if float(h.get("relevance", 0)) < floor:
            continue
        slug = str(h.get("slug", "")).strip()
        last = state["seen"].get(slug)
        if slug and last is not None and turn - int(last) < cooldown:
            continue
        picked.append(h)
        if len(picked) >= topn:
            break

    if not picked:
        _save_state(state_path, state)
        return ""

    for h in picked:
        slug = str(h.get("slug", "")).strip()
        if slug:
            state["seen"][slug] = turn
    _save_state(state_path, state)

    _append_inject_trace(kb_root, agent_id, session_id, query, picked, source="posttool")

    out = ['<recalled-memory source="oks-posttool">']
    out.append(f'<!-- query="{query}" floor={floor} (PostToolUse supplement, long-task blind-spot fill) -->')
    for h in picked:
        body = str(h.get("body_preview", ""))[:280]
        out.append(
            f"- [{h.get('type', '')}] {h.get('title', '')} "
            f"(slug: {h.get('slug', '')}, rel: {h.get('relevance', 0)})"
        )
        out.append(f"  {body}")
    out.append("</recalled-memory>")
    return "\n".join(out)


def main() -> int:
    payload = _load_payload()
    tool_name = str(payload.get("tool_name", "") or "")
    tool_input = payload.get("tool_input", {}) or {}
    if not isinstance(tool_input, dict):
        return 0
    kb_root = _kb_root()
    if kb_root is None:
        return 0
    cwd = str(payload.get("cwd", "") or "") or str(os.getcwd())
    agent_id = _agent_id(payload, cwd)
    session_id = str(payload.get("session_id", "") or "") or cwd

    output_parts = []

    # 1. File conflict detection (Edit/Write/MultiEdit only)
    if tool_name in EDIT_TOOLS:
        file_path = str(tool_input.get("file_path", "") or "")
        if file_path:
            _append_file_edit(kb_root, agent_id, file_path)
            other = _check_conflict(kb_root, agent_id, file_path)
            if other:
                _write_conflict_mail(kb_root, agent_id, file_path, other)
                output_parts.append(
                    f"[oks] 文件冲突: {Path(file_path).name} 也被 "
                    f"{other.get('agent_id')} 编辑"
                )

    # 2. Recall supplement (any tool — long-task blind spot)
    # Set OKS_POSTTOOL_RECALL=0 to disable (keep conflict detection only).
    recall_on = os.environ.get("OKS_POSTTOOL_RECALL", "1") != "0"
    if recall_on:
        query = _query_from_tool(tool_name, tool_input)
        if query:
            block = _recall_supplement(kb_root, session_id, query, agent_id)
            if block:
                output_parts.append(block)

    if output_parts:
        sys.stdout.write("\n".join(output_parts) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
