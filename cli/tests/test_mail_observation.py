"""Contract tests for the read-only collaboration overview and Thread facts."""
import base64
from datetime import datetime, timedelta, timezone
import itertools
import json

import pytest

from knowledge_studio import mail
from knowledge_studio.mail_observation import overview_data, thread_observation


@pytest.fixture(autouse=True)
def deterministic_timestamps(monkeypatch):
    counter = itertools.count()
    origin = datetime(2026, 10, 14, tzinfo=timezone.utc)
    monkeypatch.setattr(mail, "iso_now", lambda: (origin + timedelta(seconds=next(counter))).isoformat())


def _message(root, *, sender="writer", to="human", title="Visible work", body="Message body", **kwargs):
    return mail.write_message(
        root, sender=sender, recipients=to, title=title, body=body,
        origin_machine_id="observation-test-machine", **kwargs,
    )


def _present(root, message, session, agent, *, delivered=True, machine="test-machine-a"):
    row = mail.parse_message(message["path"])
    return mail.record_delivery(root, session, row, agent_id=agent, machine_id=machine, delivered=delivered)


def _ack(root, message, session, agent, *, machine="test-machine-a"):
    return mail.acknowledge_delivery(root, session, message["message_id"], agent_id=agent, machine_id=machine)


def test_visibility_applies_before_titles_counts_and_search(tmp_path):
    hidden = _message(tmp_path, to="private-reviewer", title="Secret title", body="hidden-marker", record_kind="blocked")
    _message(tmp_path, title="Public title", thread_id=hidden["thread_id"], record_kind="result")
    _message(tmp_path, sender="human", to="reviewer", title="Sent by viewer", record_kind="handoff")
    _message(tmp_path, to="private-reviewer", title="Entirely private", record_kind="handoff")

    data = overview_data(tmp_path)
    assert data["schema"] == "mail.overview.v1"
    assert {key: data["scope"][key] for key in ("viewer", "label", "coverage")} == {
        "viewer": "@human", "label": "仅包含当前 human 可见的协作记录", "coverage": "all_visible_history",
    }
    assert data["counts"] == {"threads": 2, "awaiting_receipt": 1, "with_blockers": 0, "with_results": 1, "matched": 2}
    assert {item["title"] for item in data["items"]} == {"Public title", "Sent by viewer"}
    assert all(item["message_count"] == 1 for item in data["items"])
    assert overview_data(tmp_path, query="hidden-marker")["items"] == []
    assert overview_data(tmp_path, query="Secret title")["items"] == []
    assert overview_data(tmp_path, query="@private-reviewer")["items"] == []
    assert overview_data(tmp_path, query="@REVIEWER")["counts"]["matched"] == 1
    assert "Secret" not in json.dumps(data)


def test_no_receipt_and_injected_only_do_not_claim_presentation(tmp_path):
    handoff = _message(tmp_path, sender="human", to="reviewer", record_kind="handoff")
    recipient = overview_data(tmp_path)["items"][0]["handoff"]["recipients"][0]
    assert recipient["state"] == "unobserved"
    assert recipient["presented_at"] is None
    assert recipient["sessions"] == []

    _present(tmp_path, handoff, "injected-session", "reviewer", delivered=False)
    data = overview_data(tmp_path, filter_kind="awaiting")
    recipient = data["items"][0]["handoff"]["recipients"][0]
    assert recipient["state"] == "unobserved"
    assert recipient["sessions"][0]["injected_at"]
    assert recipient["presented_at"] is None

    _present(tmp_path, handoff, "injected-session", "reviewer")
    recipient = overview_data(tmp_path)["items"][0]["handoff"]["recipients"][0]
    assert recipient["state"] == "presented"
    assert recipient["presented_at"]
    assert recipient["acknowledged_at"] is None
    assert overview_data(tmp_path, filter_kind="awaiting")["items"] == []

    _ack(tmp_path, handoff, "injected-session", "reviewer")
    recipient = overview_data(tmp_path)["items"][0]["handoff"]["recipients"][0]
    assert recipient["state"] == "acknowledged"
    assert recipient["acknowledged_at"]


def test_parallel_recipients_and_sessions_keep_independent_evidence(tmp_path):
    handoff = _message(tmp_path, sender="human", to="reviewer,worker", record_kind="handoff")
    _present(tmp_path, handoff, "review-a", "reviewer")
    _ack(tmp_path, handoff, "review-a", "reviewer")
    _present(tmp_path, handoff, "review-b", "reviewer", machine="test-machine-b")
    data = overview_data(tmp_path)
    recipients = {row["agent_id"]: row for row in data["items"][0]["handoff"]["recipients"]}
    assert recipients["@reviewer"]["state"] == "acknowledged"
    assert recipients["@worker"]["state"] == "unobserved"
    assert {session["session_id"] for session in recipients["@reviewer"]["sessions"]} == {"review-a", "review-b"}
    assert {session["machine_id"] for session in recipients["@reviewer"]["sessions"]} == {"test-machine-a", "test-machine-b"}
    assert recipients["@worker"]["sessions"] == []
    assert data["counts"]["awaiting_receipt"] == 1

    mail.update_recipient_state(tmp_path, "worker", handoff["message_id"], read_at=mail.iso_now())
    data = overview_data(tmp_path)
    worker = next(row for row in data["items"][0]["handoff"]["recipients"] if row["agent_id"] == "@worker")
    assert worker["state"] == "read"
    assert worker["read_at"]
    assert worker["presented_at"] is None
    assert data["counts"]["awaiting_receipt"] == 0


def test_blockers_have_only_direct_visible_followups_and_never_resolve(tmp_path):
    blocked = _message(tmp_path, body="Missing source material", record_kind="blocked")
    thread = blocked["thread_id"]
    unrelated = _message(tmp_path, body="Later chronology is not a reply", thread_id=thread)
    reply = _message(tmp_path, sender="human", to="writer", body="I will look", thread_id=thread, reply_to=blocked["message_id"])
    _message(tmp_path, to="private-reviewer", title="Hidden followup", thread_id=thread, reply_to=blocked["message_id"])
    nested = _message(tmp_path, body="Reply to follow-up", thread_id=thread, reply_to=reply["message_id"])
    _message(tmp_path, body="Missing parent", thread_id=thread, reply_to="not-visible")
    rows = mail.thread_messages(tmp_path, thread, "human")

    observation = thread_observation(tmp_path, rows)
    assert observation["blockers"] == [{
        "message_id": blocked["message_id"], "from": "@writer", "timestamp": blocked["meta"]["timestamp"],
        "summary": "Missing source material", "follow_up_message_ids": [reply["message_id"]],
    }]
    assert observation["links"] == [
        {"from_message_id": blocked["message_id"], "to_message_id": reply["message_id"], "kind": "reply"},
        {"from_message_id": reply["message_id"], "to_message_id": nested["message_id"], "kind": "reply"},
    ]
    assert unrelated["message_id"] not in json.dumps(observation)
    assert "resolved" not in json.dumps(observation)
    data = overview_data(tmp_path, filter_kind="blocked")
    assert data["counts"]["with_blockers"] == 1
    assert data["items"][0]["blockers"] == {"total": 1, "with_follow_up": 1}
    assert overview_data(tmp_path, filter_kind="results")["items"] == []


def test_awaiting_filter_preserves_historical_handoff_without_task_inference(tmp_path):
    old = _message(tmp_path, sender="human", to="reviewer", record_kind="handoff")
    latest = _message(tmp_path, sender="human", to="worker", record_kind="handoff", thread_id=old["thread_id"])
    _present(tmp_path, latest, "worker-session", "worker")
    _message(tmp_path, record_kind="result", thread_id=old["thread_id"])

    data = overview_data(tmp_path, filter_kind="awaiting")
    assert data["counts"]["awaiting_receipt"] == 1
    assert data["counts"]["with_results"] == 1
    assert data["items"][0]["handoff"]["message_id"] == latest["message_id"]
    assert "task_status" not in json.dumps(data)
    assert "online" not in json.dumps(data)


def test_handoff_replies_keep_recipient_and_receipt_evidence_separate(tmp_path):
    handoff = _message(tmp_path, sender="human", to="reviewer,worker", record_kind="handoff")
    reply = _message(tmp_path, sender="reviewer", to="human", thread_id=handoff["thread_id"],
                     reply_to=handoff["message_id"], record_kind="acknowledgement")
    _message(tmp_path, sender="bystander", to="human", thread_id=handoff["thread_id"],
             reply_to=handoff["message_id"])
    _message(tmp_path, sender="worker", to="human", reply_to=handoff["message_id"])
    _message(tmp_path, sender="worker", to="private-peer", thread_id=handoff["thread_id"],
             reply_to=handoff["message_id"])
    rows = mail.thread_messages(tmp_path, handoff["thread_id"], "human")
    observation = thread_observation(tmp_path, rows)
    recipients = {row["agent_id"]: row for row in observation["handoffs"][0]["recipients"]}
    assert recipients["@reviewer"]["reply_message_ids"] == [reply["message_id"]]
    assert recipients["@reviewer"]["state"] == "unobserved"
    assert recipients["@worker"]["reply_message_ids"] == []
    assert observation["links"] == [{"from_message_id": handoff["message_id"],
                                       "to_message_id": reply["message_id"], "kind": "reply"}]


@pytest.mark.parametrize("kind", ["goal", "review_request", "acknowledgement"])
def test_explicit_collaboration_fact_is_in_overview(tmp_path, kind):
    item = _message(tmp_path, record_kind=kind)
    data = overview_data(tmp_path, filter_kind="collaboration")
    assert data["items"][0]["thread_id"] == item["thread_id"]
    assert data["items"][0]["record_kinds"] == [kind]


def test_full_history_search_exceeds_snapshot_body_message_and_thread_bounds(tmp_path):
    old = _message(tmp_path, body="x" * 5000 + " needle-after-5000", title="Original title")
    for index in range(55):
        _message(tmp_path, thread_id=old["thread_id"], title=f"Later title {index}")
    for index in range(101):
        _message(tmp_path, title=f"Unrelated thread {index}")

    data = overview_data(tmp_path, query="needle-after-5000")
    assert data["counts"]["threads"] == 102
    assert data["counts"]["matched"] == 1
    assert data["items"][0]["thread_id"] == old["thread_id"]
    assert data["items"][0]["message_count"] == 56
    assert data["items"][0]["match"]["message_id"] == old["message_id"]
    assert "needle-after-5000" in data["items"][0]["match"]["preview"]
    assert "needle-after-5000" not in data["items"][0]["latest"]["preview"]
    assert overview_data(tmp_path, query="ORIGINAL TITLE")["counts"]["matched"] == 1
    assert len(overview_data(tmp_path, limit=1000)["items"]) == 100
    assert overview_data(tmp_path, limit=1000)["page"]["limit"] == 100


def test_cursor_uses_stable_sort_anchor_when_newer_threads_or_messages_arrive(tmp_path):
    old = _message(tmp_path, thread_id="thread-a")
    middle = _message(tmp_path, thread_id="thread-b")
    newest = _message(tmp_path, thread_id="thread-c")
    first = overview_data(tmp_path, limit=1)
    assert first["items"][0]["thread_id"] == newest["thread_id"]
    cursor = first["page"]["next_cursor"]
    _message(tmp_path, title="New thread", thread_id="thread-d")
    _message(tmp_path, body="New message in already seen Thread", thread_id=newest["thread_id"])

    second = overview_data(tmp_path, limit=1, cursor=cursor)
    assert second["items"][0]["thread_id"] == middle["thread_id"]
    third = overview_data(tmp_path, limit=1, cursor=second["page"]["next_cursor"])
    assert third["items"][0]["thread_id"] == old["thread_id"]
    assert third["page"] == {"limit": 1, "next_cursor": "", "has_more": False}
    assert third["counts"]["matched"] == 3
    assert third["scope"]["message_cutoff"] == first["scope"]["message_cutoff"]


def test_cursor_preserves_unseen_thread_when_new_message_would_move_it_above_anchor(tmp_path):
    old = _message(tmp_path, thread_id="thread-a", body="Original old history")
    middle = _message(tmp_path, thread_id="thread-b")
    _message(tmp_path, thread_id="thread-c")
    first = overview_data(tmp_path, limit=1)
    _message(tmp_path, thread_id=old["thread_id"], body="New reply moves the live Thread")
    assert overview_data(tmp_path)["items"][0]["thread_id"] == old["thread_id"]

    following = overview_data(tmp_path, cursor=first["page"]["next_cursor"])
    assert [item["thread_id"] for item in following["items"]] == [middle["thread_id"], old["thread_id"]]
    assert following["items"][-1]["latest"]["message_id"] == old["message_id"]
    assert following["items"][-1]["message_count"] == 1
    assert "旧时间" in following["scope"]["pagination_note"]


def test_message_watermark_uses_message_id_for_equal_timestamps(tmp_path, monkeypatch):
    monkeypatch.setattr(mail, "iso_now", lambda: "2026-10-14T00:00:00+00:00")
    ids = iter(("msg-a", "msg-b", "msg-c"))
    monkeypatch.setattr(mail, "_message_id", lambda: next(ids))
    old = _message(tmp_path, thread_id="thread-a")
    latest = _message(tmp_path, thread_id="thread-b")
    first = overview_data(tmp_path, limit=1)
    assert first["scope"]["message_cutoff"] == {"timestamp": latest["meta"]["timestamp"], "message_id": "msg-b"}
    _message(tmp_path, thread_id=old["thread_id"], body="Same timestamp, higher message ID")

    following = overview_data(tmp_path, cursor=first["page"]["next_cursor"])
    assert following["items"][0]["latest"]["message_id"] == "msg-a"
    assert following["items"][0]["message_count"] == 1


def test_search_match_locates_title_participant_and_unicode_body(tmp_path):
    title = _message(tmp_path, title="Distinctive title")
    participant = _message(tmp_path, sender="special-reviewer")
    body = _message(tmp_path, body="ß" * 300 + " CaseFoldNeedle in long body")

    assert overview_data(tmp_path, query="distinctive")["items"][0]["match"] == {
        "message_id": title["message_id"], "preview": "Distinctive title",
    }
    assert overview_data(tmp_path, query="@special-reviewer")["items"][0]["match"] == {
        "message_id": participant["message_id"], "preview": "@special-reviewer @human",
    }
    match = overview_data(tmp_path, query="casefoldneedle")["items"][0]["match"]
    assert match["message_id"] == body["message_id"]
    assert "CaseFoldNeedle" in match["preview"]
    assert all("match" not in item for item in overview_data(tmp_path)["items"])


def test_cursor_ties_are_ordered_by_thread_id_and_context_is_validated(tmp_path, monkeypatch):
    monkeypatch.setattr(mail, "iso_now", lambda: "2026-10-14T00:00:00+00:00")
    for name in ("thread-a", "thread-c", "thread-b"):
        _message(tmp_path, thread_id=name)
    first = overview_data(tmp_path, limit=1)
    assert first["items"][0]["thread_id"] == "thread-c"
    cursor = first["page"]["next_cursor"]
    assert overview_data(tmp_path, cursor=cursor)["items"][0]["thread_id"] == "thread-b"
    for kwargs in ({"agent_id": "writer"}, {"filter_kind": "blocked"}, {"query": "different"}):
        with pytest.raises(ValueError, match="cursor"):
            overview_data(tmp_path, cursor=cursor, **kwargs)
    with pytest.raises(ValueError, match="cursor"):
        overview_data(tmp_path / "other-root", cursor=cursor)
    for invalid in ("not-base64!", "e30", base64.urlsafe_b64encode(b"[1,2,3,4]").decode(), "x" * 5000):
        with pytest.raises(ValueError, match="cursor"):
            overview_data(tmp_path, cursor=invalid)
    for limit in (0, -1, True, 1.5, "50"):
        with pytest.raises(ValueError, match="limit"):
            overview_data(tmp_path, limit=limit)
    with pytest.raises(ValueError, match="filter"):
        overview_data(tmp_path, filter_kind="completed")


def test_evidence_counts_deduplicate_visible_references_and_projection_is_read_only(tmp_path):
    ref = {"type": "wiki", "path": "wiki/concept.md"}
    first = _message(tmp_path, evidence_refs=[ref])
    _message(tmp_path, thread_id=first["thread_id"], evidence_refs=[ref, {"type": "trace", "id": "run-1"}])
    _message(tmp_path, to="private-reviewer", thread_id=first["thread_id"], evidence_refs=[{"type": "trace", "id": "private"}])
    before = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    assert overview_data(tmp_path)["items"][0]["evidence_count"] == 2
    thread_observation(tmp_path, mail.thread_messages(tmp_path, first["thread_id"], "human"))
    after = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert before == after


def test_empty_root_is_read_only_and_has_complete_empty_response(tmp_path):
    root = tmp_path / "absent-kb"
    data = overview_data(root)
    assert data["items"] == []
    assert all(value == 0 for value in data["counts"].values())
    assert data["partial"] is False
    assert data["page"] == {"limit": 50, "next_cursor": "", "has_more": False}
    assert thread_observation(root, [])["handoffs"] == []
    assert not root.exists()
