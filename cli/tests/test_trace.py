"""Tests for execution traces, feedback, and proposal gates."""
import json
from concurrent.futures import ThreadPoolExecutor

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


def test_credential_like_values_are_rejected(kb):
    start_trace("goal-memory", "run-values")
    with pytest.raises(ValueError, match="aws-access-key"):
        append_event("run-values", "tool_observation", "tool", {"stdout": "key=AKIAIOSFODNN7EXAMPLE found"})
    with pytest.raises(ValueError, match="github-token"):
        append_event("run-values", "tool_observation", "tool", {"log": ["ghp_0123456789abcdefghijABCDEF"]})
    with pytest.raises(ValueError, match="private-key-block"):
        append_event("run-values", "tool_observation", "tool", {"dump": "-----BEGIN RSA PRIVATE KEY-----"})
    with pytest.raises(ValueError, match="evidence_refs"):
        append_event(
            "run-values", "retrieval", "agent", {"query": "ok"},
            ["https://ghp_0123456789abcdefghijABCDEF@github.com/o/r.git"],
        )
    assert validate_trace("run-values")["event_count"] == 1


def test_agent_cannot_clear_its_own_blocker(kb):
    start_trace("goal-memory", "run-selfunblock")
    append_event("run-selfunblock", "blocker", "agent", {"reason": "missing data", "needed": "dataset"})
    append_event("run-selfunblock", "ai_comment", "agent", {"comment": "trying anyway"})
    assert show_trace("run-selfunblock")["manifest"]["status"] == "blocked"
    append_event("run-selfunblock", "checkpoint", "human", {"action": "reviewed"})
    assert show_trace("run-selfunblock")["manifest"]["status"] == "running"


def test_concurrent_appends_keep_unique_sequences(kb):
    start_trace("goal-memory", "run-concurrent")
    with ThreadPoolExecutor(max_workers=8) as pool:
        events = list(pool.map(
            lambda i: append_event("run-concurrent", "ai_action", "agent", {"step": i}),
            range(16),
        ))
    sequences = sorted(event["sequence"] for event in events)
    assert sequences == list(range(2, 18))
    assert validate_trace("run-concurrent")["valid"] is True


def test_proposal_is_not_orphaned_when_run_completed(kb):
    start_trace("goal-memory", "run-done")
    finish_trace("run-done", {"outcome": "success"})
    with pytest.raises(ValueError, match="already completed"):
        create_proposal("run-done", "wiki", "Late lesson", "Should not land.")
    assert not (kb / "drafts" / "proposals").exists()


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
