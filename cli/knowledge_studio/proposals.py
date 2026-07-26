"""Proposal-only bridge from execution traces to reviewable memory drafts."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import yaml

from knowledge_studio.store import _atomic_write, drafts_dir, repo_root
from knowledge_studio.trace import append_event, load_manifest

PROPOSAL_KINDS = {"wiki", "skill"}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "proposal"


def create_proposal(run_id: str, kind: str, title: str, summary: str) -> Path:
    """Create a review artifact only; never mutate wiki/ or skills."""
    if kind not in PROPOSAL_KINDS:
        raise ValueError("kind must be one of: wiki, skill")
    manifest = load_manifest(run_id)
    directory = drafts_dir() / "proposals" / kind
    path = directory / f"{run_id}-{_slugify(title)}.md"
    if path.exists():
        raise FileExistsError(f"Proposal already exists: {path}")
    created = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    meta = {
        "title": title, "proposal_kind": kind, "status": "proposal",
        "source_run": run_id, "source_goal": manifest["goal_id"],
        "created": created, "human_approved": False,
    }
    body = (
        "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).rstrip() +
        "\n---\n\n# " + title + "\n\n## Summary\n\n" + summary.strip() +
        "\n\n## Review\n\n- [ ] Human reviewed evidence\n"
        "- [ ] Human approved promotion\n\n"
        "> This file is a proposal. It is not applied to wiki/ or any skill directory.\n"
    )
    _atomic_write(path, body)
    append_event(
        run_id, "proposal", "agent",
        {"kind": kind, "title": title, "path": path.relative_to(repo_root()).as_posix()},
        [manifest["trace_path"]],
    )
    return path
