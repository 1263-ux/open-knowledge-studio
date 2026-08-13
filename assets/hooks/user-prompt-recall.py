#!/usr/bin/env python3
"""UserPromptSubmit hook — auto-recall memory + goals + mail, inject as context.

Reads the editor's UserPromptSubmit JSON payload on stdin (Claude Code and Qoder
share the same `.prompt` contract), runs the OKS recall engine against the user's
prompt, reads active goals + unread mail, and prints a structured
<recalled-memory> block on stdout (which the editor adds to the model's context).
Fails open: any error or empty result prints nothing and exits 0, so it never
blocks a prompt.

Tunables via env:
  OKS_RECALL_FLOOR     min knowledge relevance to inject (default 0.7)
  OKS_RECALL_TOPN      max knowledge memories injected (default 3)
  OKS_RECALL_MINLEN    skip prompts shorter than this many chars (default 6)
  OKS_RECALL_COOLDOWN  turns before the same slug may be re-injected (default 10)
  OKS_MAIL_TOPN        max unread mail injected (default 3)
"""
import json
import os
import re
import sys
from pathlib import Path

_TRIVIAL = {
    "你好", "谢谢", "多谢", "ok", "okay", "好", "好的", "嗯", "行", "继续",
    "hi", "hello", "thanks", "thx", "yes", "no", "是", "对", "收到",
}


def _load_payload() -> dict:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _kb_root() -> Path | None:
    """Locate the knowledge base root: OKS_ROOT -> config -> cwd."""
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


def _state_path(session_id: str, kb_root: Path) -> Path:
    """Persist cooldown state inside the KB (.oks/) so it survives restarts."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[:80] or "default"
    state_dir = kb_root / ".oks"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / f"recall-state-{safe}.json"


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
        path.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass  # state is best-effort; dedup degrades gracefully


def _load_active_goals(kb_root: Path) -> list:
    """Read profiles/goals/*.md with status: active. Returns title/slug/keywords."""
    goals_dir = kb_root / "profiles" / "goals"
    if not goals_dir.is_dir():
        return []
    goals = []
    for f in sorted(goals_dir.glob("*.md")):
        try:
            text = f.read_text(encoding="utf-8")
            parts = text.split("---")
            if len(parts) >= 2 and "status: active" in parts[1]:
                title = f.stem
                keywords = []
                in_kw = False
                for line in parts[1].split("\n"):
                    if line.startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip("\"'")
                    elif line.startswith("keywords:"):
                        in_kw = True
                    elif in_kw:
                        s = line.strip()
                        if s.startswith("- "):
                            keywords.append(s[2:].strip())
                        elif s and not line.startswith(" "):
                            in_kw = False
                goals.append({"title": title, "slug": f.stem, "keywords": keywords})
        except Exception:
            continue
    return goals


def _load_unread_mail(kb_root: Path, limit: int = 3) -> list:
    """Read mail/inbox/*.md with read: false, newest first."""
    inbox = kb_root / "mail" / "inbox"
    if not inbox.is_dir():
        return []
    mails = []
    for f in sorted(inbox.glob("*.md"), reverse=True):
        try:
            text = f.read_text(encoding="utf-8")
            parts = text.split("---")
            if len(parts) >= 3 and "read: false" in parts[1]:
                from_id = "unknown"
                title = ""
                for line in parts[1].split("\n"):
                    if line.startswith("from:"):
                        from_id = line.split(":", 1)[1].strip()
                for line in parts[2].split("\n"):
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                preview = re.sub(r"\s+", " ", parts[2].split("\n", 1)[-1]).strip()[:100]
                mails.append({
                    "slug": f.stem, "from": from_id, "title": title,
                    "preview": preview, "path": f,
                })
                if len(mails) >= limit:
                    break
        except Exception:
            continue
    return mails


def _mark_mail_read(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8")
        text = text.replace("read: false", "read: true", 1)
        path.write_text(text, encoding="utf-8")
    except Exception:
        pass


def main() -> int:
    payload = _load_payload()
    prompt = str(payload.get("prompt", "") or "").strip()
    if not prompt:
        return 0

    minlen = int(os.environ.get("OKS_RECALL_MINLEN", "6"))
    if len(prompt) < minlen or prompt.lower() in _TRIVIAL:
        return 0

    kb_root = _kb_root()
    if kb_root is None:
        return 0  # no KB to recall from — fail open

    session_id = str(payload.get("session_id", "") or "")
    state_file = _state_path(session_id, kb_root)
    state = _load_state(state_file)
    is_first_turn = state.get("n", 0) == 0

    # ── Knowledge section (6+1 recall + cooldown) — compute first so we
    # know whether the query is on-scope for any active goal ──
    try:
        from knowledge_studio.recall import recall
    except Exception:
        recall = None  # engine unavailable — still show goals + mail

    picked: list = []
    goal_relevant = False

    if recall is not None:
        floor = float(os.environ.get("OKS_RECALL_FLOOR", "0.7"))
        topn = int(os.environ.get("OKS_RECALL_TOPN", "3"))
        cooldown = int(os.environ.get("OKS_RECALL_COOLDOWN", "10"))

        state["n"] += 1
        turn = state["n"]

        try:
            # over-fetch to leave room for cooldown skips (补位)
            hits = recall(query=prompt, limit=max(topn * 3, 10)).get("knowledge", [])
        except Exception:
            hits = []

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

        if picked:
            for h in picked:
                slug = str(h.get("slug", "")).strip()
                if slug:
                    state["seen"][slug] = turn
            # goal 相关性：picked 有 goal boost 说明 query 与 goal 相关
            for h in picked:
                c = h.get("score_components", {})
                if c.get("goal_area", 0) > 0 or c.get("goal_keyword", 0) > 0:
                    goal_relevant = True
                    break
        _save_state(state_file, state)

    # goal 相关性双重判断：query 和 goal keywords 直接匹配（不依赖 picked，
    # 避免 cooldown 补位到非 goal 域页时漏判）
    if not goal_relevant:
        prompt_lower = prompt.lower()
        for g in _load_active_goals(kb_root):
            for kw in g.get("keywords", []):
                if kw.lower() in prompt_lower:
                    goal_relevant = True
                    break
            if goal_relevant:
                break

    # ── Build sections in order: goal -> knowledge -> mail ──
    sections = []

    # Goal section: 首次提醒 (新 session) or 按需 (query 与 goal 相关才注入)
    # 不相关时不占上下文
    if is_first_turn or goal_relevant:
        goals = _load_active_goals(kb_root)
        if goals:
            lines = ["## 当前目标"]
            if is_first_turn and not goal_relevant:
                lines.append("(首次提醒 — 之后只在 query 与 goal 相关时注入)")
            for g in goals:
                lines.append(f"[goal] {g['title']} ({g['slug']})")
            sections.append("\n".join(lines))

    # Knowledge section
    if picked:
        lines = [
            "## 相关记忆",
            "相关已沉淀记忆（引用时用 slug；与当前事实冲突以最新为准）：",
        ]
        for h in picked:
            title = str(h.get("title", h.get("slug", ""))).strip()
            slug = str(h.get("slug", "")).strip()
            htype = str(h.get("type", "")).strip()
            rel = float(h.get("relevance", 0))
            preview = re.sub(r"\s+", " ", str(h.get("body_preview", ""))).strip()[:160]
            lines.append(f"- [{htype}] {title} ({slug}) rel={rel:.2f}")
            if preview:
                lines.append(f"    {preview}")
        sections.append("\n".join(lines))

    # ── Mail section (unread, mark as read after inject) ──
    mail_topn = int(os.environ.get("OKS_MAIL_TOPN", "3"))
    mails = _load_unread_mail(kb_root, limit=mail_topn)
    if mails:
        lines = [f"## 通信（{len(mails)} 未读）"]
        for m in mails:
            lines.append(f"[mail] [@{m['from']}] {m['title']} — {m['slug']}")
            if m["preview"]:
                lines.append(f"    {m['preview']}")
        sections.append("\n".join(lines))
        for m in mails:
            _mark_mail_read(m["path"])

    if not sections:
        return 0

    out = ['<recalled-memory source="oks">']
    out.extend(sections)
    out.append("</recalled-memory>")
    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
