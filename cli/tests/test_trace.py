"""Tests for execution traces, feedback, and proposal gates."""
import json

import pytest

from knowledge_studio.proposals import create_proposal
from knowledge_studio.trace import append_event, finish_trace, show_trace, start_trace, validate_trace


@pytest.fixture
def kb(tmp_path, monkeypatch):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    (tmp_path / "raw").mkdir()
    (tmp_path / "wiki").mkdir()
    (tmp_path / "drafts").mkdir()
    return tmp_path


def test_complete_trace_is_append_only_and_valid(kb):
    start_trace("goal-memory", "run-001")
    append_event("run-001", "retrieval", "agent", {"query": "memory"}, ["wiki/page.md"])
    append_event("run-001", "tool_observation", "tool", {"exit_code": 0})
    append_event("run-001", "judge_comment", "judge", {"outcome": "pass"})
    append_event("run-001", "human_comment", "human", {"outcome": "accepted"})
    finish_trace("run-001", {"outcome": "success"})

    result = validate_trace("run-001", require_completed=True)
    trace = show_trace("run-001")
    assert result["valid"] is True
    assert [event["sequence"] for event in trace["events"]] == list(range(1, 7))
    assert trace["manifest"]["status"] == "completed"
    with pytest.raises(ValueError, match="already completed"):
        append_event("run-001", "ai_comment", "agent", {"comment": "late"})


def test_sensitive_fields_are_rejected(kb):
    start_trace("goal-memory", "run-secret")
    with pytest.raises(ValueError, match="Sensitive field"):
        append_event("run-secret", "tool_observation", "tool", {"authorization": "Bearer secret"})
    with pytest.raises(ValueError, match="Sensitive field"):
        append_event("run-secret", "tool_observation", "tool", {"auth": {"github_token": "secret"}})
    with pytest.raises(ValueError, match="Sensitive field"):
        append_event("run-secret", "tool_observation", "tool", {"client_secret": "secret"})
    assert validate_trace("run-secret")["event_count"] == 1


def test_finish_requires_supported_outcome(kb):
    start_trace("goal-memory", "run-outcome")
    with pytest.raises(ValueError, match="result.outcome"):
        finish_trace("run-outcome", {"outcome": "maybe"})


def test_blocker_status_and_resume(kb):
    start_trace("goal-memory", "run-blocked")
    append_event("run-blocked", "blocker", "agent", {"reason": "missing data", "needed": "dataset"})
    assert show_trace("run-blocked")["manifest"]["status"] == "blocked"
    append_event("run-blocked", "human_action", "human", {"action": "provided dataset"})
    assert show_trace("run-blocked")["manifest"]["status"] == "running"


def test_proposal_never_mutates_formal_wiki_or_skill(kb):
    start_trace("goal-memory", "run-proposal")
    before = sorted(path.relative_to(kb).as_posix() for path in (kb / "wiki").rglob("*"))
    path = create_proposal("run-proposal", "wiki", "Recall lesson", "Prefer reproducible goal selection.")
    assert path.is_file()
    assert "human_approved: false" in path.read_text(encoding="utf-8")
    assert sorted(item.relative_to(kb).as_posix() for item in (kb / "wiki").rglob("*")) == before
    assert not (kb / ".claude" / "skills").exists()
    last = json.loads((kb / "raw" / "executions" / "run-proposal" / "events.jsonl").read_text().splitlines()[-1])
    assert last["event_type"] == "proposal"
