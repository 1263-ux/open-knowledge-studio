"""Focused tests for the file-backed Mail domain and runtime seam."""
import json

import pytest

from knowledge_studio import mail
from knowledge_studio.mail_runtime import FileMailRuntime


def _message(root, *, sender="writer", to="reviewer", body="正文", thread_id=""):
    return mail.write_message(
        root,
        body=body,
        sender=sender,
        sender_kind="agent",
        recipients=to,
        title="讨论",
        thread_id=thread_id,
        origin_session_id=f"session-{sender}",
        origin_machine_id=f"machine-{sender}",
    )


def test_message_is_canonical_and_thread_visible(tmp_path):
    first = _message(tmp_path)
    second = _message(tmp_path, sender="reviewer", to="writer", thread_id=first["thread_id"], body="回复")

    assert first["path"].parent == tmp_path / "mail" / "messages"
    assert [item["body"] for item in mail.thread_messages(tmp_path, first["thread_id"], "writer")] == ["正文", "回复"]
    assert json.loads(first["path"].read_text(encoding="utf-8").split("evidence_refs: ", 1)[1].splitlines()[0]) == []
    assert second["meta"]["sender_kind"] == "agent"


def test_session_receipt_is_at_most_once_and_acknowledge_is_explicit(tmp_path):
    runtime = FileMailRuntime(tmp_path, "reviewer", "ses-1", "machine-a")
    sent = _message(tmp_path, to="reviewer")
    runtime.register(scope="review")

    first = runtime.wait(timeout=0)
    second = runtime.wait(timeout=0)
    assert first["status"] == "messages"
    assert first["messages"][0]["receipt"]["status"] == "presented"
    assert second["status"] == "timeout"
    assert runtime.ack(sent["message_id"])["status"] == "acknowledged"
    assert runtime.ack(sent["message_id"])["status"] == "acknowledged"


def test_receipt_rejects_wrong_agent_or_machine(tmp_path):
    owner = FileMailRuntime(tmp_path, "reviewer", "ses-1", "machine-a")
    sent = _message(tmp_path, to="reviewer")
    owner.wait(timeout=0)
    with pytest.raises(PermissionError):
        mail.acknowledge_delivery(tmp_path, "ses-1", sent["message_id"], agent_id="other", machine_id="machine-a")
    with pytest.raises(PermissionError):
        mail.acknowledge_delivery(tmp_path, "ses-1", sent["message_id"], agent_id="reviewer", machine_id="machine-b")


def test_runtime_delegate_is_a_normal_handoff_message(tmp_path):
    runtime = FileMailRuntime(tmp_path, "writer", "ses-1", "machine-a")
    result = runtime.delegate(task="检查接口", to="reviewer", context="带上日志", acceptance="回复结论")
    message = mail.parse_message(result["path"])
    assert result["operation"] == "delegate"
    assert message["meta"]["type"] == "handoff"
    assert "## 验收条件" in message["body"]


def test_invalid_candidate_evidence_path_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        mail.write_message(
            tmp_path,
            body="x",
            sender="writer",
            sender_kind="agent",
            recipients="reviewer",
            evidence_refs=[{"type": "candidate", "path": "../secret"}],
        )


def test_legacy_date_organized_inbox_remains_readable(tmp_path):
    path = tmp_path / "mail" / "inbox" / "2026" / "09" / "11" / "legacy.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nfrom: writer\nto: reviewer\nread: false\n---\n\n# Legacy\n\nbody\n", encoding="utf-8")
    messages = list(mail.iter_messages(tmp_path, "reviewer"))
    assert len(messages) == 1
    assert messages[0]["title"] == "Legacy"
