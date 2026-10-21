import json

import pytest

from knowledge_studio import mail
from knowledge_studio.mail_activity import activity_data, delivery_records


def test_activity_projects_real_receipts_without_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("OKS_MACHINE_ID", "machine-a")
    result = mail.write_message(tmp_path, sender="human", recipients="writer,reviewer", title="讨论", body="请确认")
    row = next(mail.iter_messages(tmp_path, "writer"))
    mail.record_delivery(tmp_path, "writer-s1", row, agent_id="writer")
    mail.acknowledge_delivery(tmp_path, "writer-s1", result["message_id"], agent_id="writer")
    mail.write_message(tmp_path, sender="writer", recipients="human", sender_kind="agent",
                       thread_id=result["thread_id"], reply_to=result["message_id"], body="已处理")
    before = {str(path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    data = activity_data(tmp_path)
    assert {event["type"] for event in data["events"]} == {"message", "reply", "presented", "acknowledged"}
    delivery = delivery_records(tmp_path, [row])[result["message_id"]]
    assert next(item for item in delivery if item["agent_id"] == "@writer")["sessions"][0]["acknowledged_at"]
    assert next(item for item in delivery if item["agent_id"] == "@reviewer")["sessions"] == []
    assert next(member for member in data["members"] if member["id"] == "@writer")["kind"] == "agent"
    assert data["scope"] == "human-visible-history"
    assert before == {str(path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}


def test_receipt_lifecycle_ignores_random_filename_order(tmp_path, monkeypatch):
    monkeypatch.setenv("OKS_MACHINE_ID", "machine-a")
    ids = iter(["evt_20261021T000000000000_ffff", "evt_20261021T000000000000_bbbb",
                "evt_20261021T000000000000_aaaa"])
    monkeypatch.setattr(mail, "_receipt_event_id", lambda: next(ids))
    result = mail.write_message(tmp_path, sender="human", recipients="writer", body="confirm")
    row = next(mail.iter_messages(tmp_path, "writer"))
    mail.record_delivery(tmp_path, "s1", row, agent_id="writer", delivered=False)
    mail.record_delivery(tmp_path, "s1", row, agent_id="writer", delivered=True)
    mail.acknowledge_delivery(tmp_path, "s1", result["message_id"], agent_id="writer")
    events = list(mail.iter_receipt_events(tmp_path, "s1", result["message_id"]))
    assert [e["event_type"] for e in events] == ["injected", "presented", "acknowledged"]
    # Event history must rebuild the snapshot even after its compatibility view is lost.
    mail.receipt_path(tmp_path, "s1", result["message_id"]).unlink()
    receipt = mail.acknowledge_delivery(tmp_path, "s1", result["message_id"], agent_id="writer")
    assert receipt["status"] == "acknowledged"
    assert len(list(mail.iter_receipt_events(tmp_path, "s1", result["message_id"]))) == 3


def test_activity_excludes_private_messages_and_unrelated_receipts(tmp_path):
    public = mail.write_message(tmp_path, sender="human", recipients="writer", title="公开", body="可见")
    private = mail.write_message(tmp_path, sender="private-a", recipients="private-b", title="保密", body="secret")
    public_row = next(mail.iter_messages(tmp_path, "human"))
    private_row = next(mail.iter_messages(tmp_path, "private-b"))
    mail.record_delivery(tmp_path, "private-session", private_row, agent_id="private-b")
    # A receipt from an unrelated identity must not appear under a visible message.
    mail.record_delivery(tmp_path, "wrong-session", public_row, agent_id="unrelated")
    mail.register_session(tmp_path, "private-session", "private-b", machine_id="private-machine")
    mail.register_session(tmp_path, "wrong-session", "unrelated", machine_id="unrelated-machine")
    mail.register_session(tmp_path, "writer-private-session", "writer", machine_id="writer-private-machine")
    mail.write_message(tmp_path, sender="writer", recipients="private-b", body="private writer activity",
                       origin_session_id="writer-private-session")
    data = activity_data(tmp_path)
    assert len(data["events"]) == 1
    assert data["events"][0]["message_id"] == public["message_id"]
    assert private["message_id"] not in json.dumps(data)
    assert {member["id"] for member in data["members"]} == {"@human", "@writer"}
    writer = next(member for member in data["members"] if member["id"] == "@writer")
    assert writer["session_count"] == 0
    assert writer["machine_ids"] == []
    assert writer["last_seen_at"] == ""
    assert "private-session" not in json.dumps(data)
    assert "private-machine" not in json.dumps(data)


def test_activity_recovers_event_only_receipts_and_ignores_broken_files(tmp_path):
    result = mail.write_message(tmp_path, sender="human", recipients="writer", body="hello")
    row = next(mail.iter_messages(tmp_path, "writer"))
    mail.record_delivery(tmp_path, "s1", row, agent_id="writer", machine_id="unknown", delivered=False)
    mail.receipt_path(tmp_path, "s1", result["message_id"]).unlink()
    sessions = mail.sessions_dir(tmp_path)
    sessions.mkdir(parents=True, exist_ok=True)
    (sessions / "broken.json").write_text("{", encoding="utf-8")
    (sessions / "list.json").write_text("[]", encoding="utf-8")
    mail.register_session(tmp_path, "s2", "writer", machine_id="machine-b")
    before_visible_origin = activity_data(tmp_path)
    assert next(member for member in before_visible_origin["members"] if member["id"] == "@writer")["machine_ids"] == []
    mail.write_message(tmp_path, sender="writer", recipients="human", body="visible session evidence",
                       origin_session_id="s2", origin_machine_id="machine-b")
    data = activity_data(tmp_path)
    assert {event["type"] for event in data["events"]} == {"message", "injected"}
    assert next(member for member in data["members"] if member["id"] == "@writer")["machine_ids"] == ["machine-b"]


def test_activity_feed_is_bounded_and_empty_state_is_real(tmp_path):
    assert activity_data(tmp_path)["events"] == []
    mail.register_session(tmp_path, "unobserved-session", "private-agent", machine_id="private-machine")
    assert activity_data(tmp_path)["members"] == []
    for number in range(4):
        mail.write_message(tmp_path, sender="human", recipients="writer", body=str(number))
    data = activity_data(tmp_path, limit=2)
    assert len(data["events"]) == 2
    assert data["truncated"] is True


@pytest.mark.parametrize("visible_source", ["message", "receipt"])
def test_shared_session_id_does_not_expose_a_different_registry_agent(tmp_path, visible_source):
    if visible_source == "message":
        mail.write_message(tmp_path, sender="writer", recipients="human", body="visible",
                           origin_session_id="shared-session")
    else:
        mail.write_message(tmp_path, sender="human", recipients="writer", body="visible")
        row = next(mail.iter_messages(tmp_path, "writer"))
        mail.record_delivery(tmp_path, "shared-session", row, agent_id="writer")
    mail.register_session(tmp_path, "shared-session", "private-agent", machine_id="private-machine")

    data = activity_data(tmp_path)
    assert {member["id"] for member in data["members"]} == {"@human", "@writer"}
    assert "private-agent" not in json.dumps(data)
    assert "private-machine" not in json.dumps(data)
    assert next(member for member in data["members"] if member["id"] == "@writer")["session_count"] == 0


@pytest.mark.parametrize("visible_source", ["message", "receipt"])
def test_last_seen_uses_visible_evidence_not_registry_heartbeat(tmp_path, monkeypatch, visible_source):
    public_time = "2026-10-14T01:00:00+00:00"
    private_time = "2026-10-14T09:00:00+00:00"
    monkeypatch.setattr(mail, "iso_now", lambda: public_time)
    if visible_source == "message":
        mail.write_message(tmp_path, sender="writer", recipients="human", body="visible",
                           origin_session_id="writer-session", origin_machine_id="public-machine")
    else:
        mail.write_message(tmp_path, sender="human", recipients="writer", body="visible")
        row = next(mail.iter_messages(tmp_path, "writer"))
        mail.record_delivery(tmp_path, "writer-session", row, agent_id="writer", machine_id="public-machine")
    monkeypatch.setattr(mail, "iso_now", lambda: private_time)
    mail.write_message(tmp_path, sender="writer", recipients="private-peer", body="private",
                       origin_session_id="writer-session")
    mail.register_session(tmp_path, "writer-session", "writer", machine_id="private-machine")

    data = activity_data(tmp_path)
    writer = next(member for member in data["members"] if member["id"] == "@writer")
    assert writer["session_count"] == 1
    assert writer["machine_ids"] == ["public-machine"]
    assert "private-machine" not in json.dumps(data)
    assert writer["last_seen_at"] == public_time
    assert private_time not in json.dumps(data)


def test_bad_utf8_receipt_and_state_do_not_break_visible_thread(tmp_path):
    result = mail.write_message(tmp_path, sender="human", recipients="writer", body="still visible")
    row = next(mail.iter_messages(tmp_path, "human"))
    receipt = mail.receipt_path(tmp_path, "broken-session", result["message_id"])
    receipt.parent.mkdir(parents=True)
    receipt.write_bytes(b"\xff")
    mail.recipient_state_path(tmp_path, "writer", result["message_id"]).write_bytes(b"\xff")
    records = delivery_records(tmp_path, [row])[result["message_id"]]
    assert records == [{"agent_id": "@writer", "read_at": None, "sessions": []}]
    assert activity_data(tmp_path)["events"][0]["excerpt"] == "still visible"


def test_all_token_in_to_is_expanded_not_projected_as_a_recipient(tmp_path):
    """A literal ``@all`` in ``to`` must not surface as a recipient.

    The current writer path expands ``@all`` inside
    :func:`mail.resolve_recipients`, so the literal token only survives in a
    message written by an older build or by another clone. The read side is
    still what decides who is shown as a recipient, so it has to expand the
    token instead of listing it beside the real agents.
    """
    result = mail.write_message(tmp_path, sender="human", recipients="writer", body="hi")
    row = next(mail.iter_messages(tmp_path, "writer"))
    mail.record_delivery(tmp_path, "writer-s1", row, agent_id="writer")
    legacy = {**row, "meta": {**row["meta"], "to": ["@all", "@writer"]}}
    agents = [
        item["agent_id"]
        for item in delivery_records(tmp_path, [legacy])[result["message_id"]]
    ]
    assert "@all" not in agents
    assert agents == ["@writer"]
