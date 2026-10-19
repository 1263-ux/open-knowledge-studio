"""Contract tests for the human timeline projection.

The point of these tests is honesty, not formatting: protocol fields must not
leak into the default reading path, and ``acknowledged`` must never be readable
as "done".
"""
import pytest

from knowledge_studio import mail, mail_timeline


@pytest.mark.parametrize("kind,expected", [("goal", "记录了一项目标"),
                                     ("review_request", "请 reviewer 查看并审核"),
                                     ("acknowledgement", "留下了一条确认记录（不代表完成）"),
                                     ("knowledge_ref", "引用了一条知识")])
def test_fact_classification_does_not_mix_reference_review_and_confirmation(kind, expected):
    action, key, _ = mail_timeline.classify({"record_kind": kind, "to": ["@reviewer"]})
    assert action == expected
    assert key


@pytest.fixture
def kb(tmp_path, monkeypatch):
    root = tmp_path / "kb"
    (root / "mail").mkdir(parents=True)
    (root / "wiki").mkdir()
    monkeypatch.setenv("OKS_MACHINE_ID", "timeline-test-machine")
    return root


def send(root, **kwargs):
    kwargs.setdefault("sender", "human")
    kwargs.setdefault("sender_kind", "human")
    kwargs.setdefault("origin_machine_id", "timeline-test-machine")
    return mail.write_message(root, **kwargs)


def find(projection, message_id):
    return next(node for node in projection["nodes"] if node["id"] == message_id)


def test_action_sentences_replace_protocol_vocabulary(kb):
    mail.register_session(kb, "sess-codex", "codex")
    handoff = send(kb, recipients=["@codex"], title="把面板做完", body="继续实现", delivery_reason="handoff", record_kind="handoff")
    review = send(kb, recipients=["@judge-agent"], title="复核口径", body="请确认", delivery_reason="review_request", record_kind="knowledge_ref")
    conflict = send(kb, recipients=["@writer-agent"], title="同一文件被改动", body="冲突", delivery_reason="conflict", record_kind="note")
    result = send(kb, recipients=["@human"], title="已完成初稿", body="写完了", delivery_reason="direct", record_kind="result")
    system = send(kb, recipients=["@all"], title="Wiki 已更新", body="已入库", delivery_reason="system", record_kind="note")

    projection = mail_timeline.timeline_data(kb)

    assert find(projection, handoff["message_id"])["action"] == "把这件事交给 codex 继续"
    assert find(projection, review["message_id"])["action"] == "请 judge-agent 查看并审核"
    assert find(projection, conflict["message_id"])["action"] == "发现文件冲突，提醒 writer-agent 一起确认"
    assert find(projection, result["message_id"])["action"] == "报告了一项结果"
    assert find(projection, system["message_id"])["action"] == "系统记录了这次协作的事实"

    # The default reading path carries no protocol vocabulary at all.
    for node in projection["nodes"]:
        for field in ("action", "result", "excerpt"):
            for token in ("handoff", "review_request", "thread_reply", "conflict", "system", "record_kind", "delivery_reason"):
                assert token not in node[field], (field, token, node[field])


def test_protocol_fields_are_kept_for_expansion_only(kb):
    sent = send(kb, recipients=["@codex"], title="复核口径", body="请确认", delivery_reason="review_request", record_kind="knowledge_ref")
    node = find(mail_timeline.timeline_data(kb), sent["message_id"])

    assert node["protocol"]["message_id"] == sent["message_id"]
    assert node["protocol"]["delivery_reason"] == "review_request"
    assert node["protocol"]["record_kind"] == "knowledge_ref"
    assert node["protocol"]["delivery_reason_label"] == "请求审核"


def test_acknowledged_is_never_phrased_as_completion(kb):
    sent = send(kb, recipients=["@research-agent"], title="请确认收到", body="只是确认读到")
    message = next(item for item in mail.iter_messages(kb, "@research-agent") if item["meta"]["message_id"] == sent["message_id"])
    mail.register_session(kb, "sess-a", "research-agent")
    mail.record_delivery(kb, "sess-a", message, agent_id="@research-agent")
    mail.acknowledge_delivery(kb, "sess-a", sent["message_id"], agent_id="@research-agent")

    node = find(mail_timeline.timeline_data(kb), sent["message_id"])
    state = node["delivery"][0]
    assert state["state"] == "acknowledged"
    assert state["state_label"] == "已确认收到（不代表完成）"
    assert "完成" not in mail_timeline.STATE_LABELS["read"]


def test_presentation_and_acknowledgement_stay_distinct(kb):
    sent = send(kb, recipients=["@writer-agent"], title="验收标准", body="请确认")
    message = next(item for item in mail.iter_messages(kb, "@writer-agent") if item["meta"]["message_id"] == sent["message_id"])
    mail.register_session(kb, "sess-w", "writer-agent")
    mail.record_delivery(kb, "sess-w", message, agent_id="@writer-agent")

    node = find(mail_timeline.timeline_data(kb), sent["message_id"])
    assert node["delivery"][0]["state"] == "notified"
    # injected and delivered share one instant for a delivered message, so the
    # stronger fact stands alone and records what it absorbed.
    steps = node["delivery"][0]["steps"]
    assert [step["step"] for step in steps] == ["presented"]
    assert steps[0]["supersedes"] == "injected"
    assert node["sessions"] == ["sess-w"]


def test_saved_message_without_receipts_does_not_claim_presentation(kb):
    sent = send(kb, recipients=["@codex"], title="待接收", body="尚无回执")

    node = find(mail_timeline.timeline_data(kb), sent["message_id"])
    assert node["delivery"][0]["state"] == "created"
    assert node["delivery"][0]["steps"] == []
    assert node["delivery_chip"]["label"] == "未观察到呈现"


def test_read_marker_and_injection_do_not_invent_presentation(kb):
    sent = send(kb, recipients=["@codex"], title="只标已读", body="没有 Session 呈现回执")
    mail.update_recipient_state(kb, "codex", sent["message_id"], read_at=mail.iso_now())
    node = find(mail_timeline.timeline_data(kb), sent["message_id"])
    assert node["delivery"][0]["state"] == "read"
    assert node["delivery"][0]["steps"] == []
    assert node["delivery_chip"]["label"] == "已标记已读"

    injected = send(kb, recipients=["@reviewer"], title="仅注入", body="兼容旧注入回执")
    message = next(item for item in mail.iter_messages(kb, "reviewer")
                   if item["meta"]["message_id"] == injected["message_id"])
    mail.record_delivery(kb, "injected-session", message, agent_id="reviewer", delivered=False)
    node = find(mail_timeline.timeline_data(kb), injected["message_id"])
    assert node["delivery"][0]["state"] == "injected"
    assert [step["step"] for step in node["delivery"][0]["steps"]] == ["injected"]
    assert node["delivery_chip"]["label"] == "已注入上下文，尚未确认"


def test_delivery_summary_does_not_extend_one_receipt_to_other_recipients(kb):
    sent = send(kb, recipients=["@ack-peer", "@shown-peer", "@unseen-peer"],
                title="多人协作", body="分别记录投递事实")
    message = next(item for item in mail.iter_messages(kb, "ack-peer")
                   if item["meta"]["message_id"] == sent["message_id"])
    mail.record_delivery(kb, "ack-session", message, agent_id="ack-peer")
    mail.acknowledge_delivery(kb, "ack-session", sent["message_id"], agent_id="ack-peer")
    mail.record_delivery(kb, "shown-session", message, agent_id="shown-peer")

    node = find(mail_timeline.timeline_data(kb), sent["message_id"])
    assert {item["peer"]: item["state"] for item in node["delivery"]} == {
        "@ack-peer": "acknowledged", "@shown-peer": "notified", "@unseen-peer": "created",
    }
    assert node["delivery_chip"] == {
        "label": "1/3 位收件人：已确认收到（不代表完成）；1/3 位收件人：已呈现，尚未确认；1/3 位收件人：未观察到呈现",
        "tone": "wait",
    }


def test_cross_session_continuation_is_flagged(kb):
    first = send(kb, recipients=["@human"], title="第一段", body="开始", origin_session_id="sess-1")
    second = send(
        kb,
        recipients=["@human"],
        title="Re: 第一段",
        body="换了个 Session 继续",
        thread_id=first["thread_id"],
        reply_to=first["message_id"],
        delivery_reason="thread_reply",
        origin_session_id="sess-2",
    )

    node = find(mail_timeline.timeline_data(kb), second["message_id"])
    assert node["cross_session"] is True
    assert node["action"] == "换了一个 Session 继续这段协作"
    assert node["key_action"] is True


def test_projection_is_bounded_and_says_so(kb):
    for index in range(5):
        send(kb, recipients=["@human"], title=f"记录 {index}", body="内容")

    projection = mail_timeline.timeline_data(kb, limit=2)
    assert projection["scope"]["truncated"] is True
    assert projection["scope"]["visible_messages"] == 5
    assert projection["scope"]["returned_nodes"] == 2
    assert len(projection["nodes"]) == 2
    # 默认阅读路径上只留一句话；完整口径收进 why（展开说明用）。
    assert projection["scope"]["note"]
    assert "不等于对方已办妥" in projection["scope"]["why"]


def test_limit_is_clamped(kb):
    send(kb, recipients=["@human"], title="记录", body="内容")
    assert mail_timeline.timeline_data(kb, limit=10 ** 6)["scope"]["limit"] == mail_timeline.MAX_LIMIT
    assert mail_timeline.timeline_data(kb, limit=0)["scope"]["limit"] == 1


def test_latest_node_summarises_where_the_collaboration_stands(kb):
    send(kb, recipients=["@human"], title="早的记录", body="一")
    send(kb, recipients=["@human"], title="晚的记录", body="二")

    projection = mail_timeline.timeline_data(kb)
    assert projection["latest"]["result"] == "晚的记录"
    assert projection["nodes"][0]["id"] == projection["latest"]["id"]


def test_empty_knowledge_base_is_an_honest_empty_state(kb):
    projection = mail_timeline.timeline_data(kb)
    assert projection["nodes"] == []
    assert projection["latest"] is None
    assert projection["counts"]["participants"] == 0


def test_stage_compatibility_fields_are_explicitly_deprecated(kb):
    projection = mail_timeline.timeline_data(kb)
    assert projection["stages"] == []
    assert projection["stages_deprecated"] is True
    assert projection["stages_coherent"] is None
    assert "已停用" in projection["stages_note"]
    assert "不能证明" in projection["stages_why"]


def test_messages_across_threads_do_not_infer_knowledge_progress(kb):
    send(kb, recipients=["@codex"], title="需求", body="请处理")
    for record_kind, reason, refs in (
        ("handoff", "handoff", []),
        ("result", "direct", []),
        ("knowledge_ref", "review_request", []),
        ("note", "system", [{"type": "wiki", "path": "wiki/result.md"}]),
    ):
        send(kb, sender="codex", sender_kind="agent", recipients=["@human"],
             title="协作记录", body="记录本身不是流程证据",
             record_kind=record_kind, delivery_reason=reason, evidence_refs=refs)

    projection = mail_timeline.timeline_data(kb)
    assert len({node["thread"]["id"] for node in projection["nodes"]}) == 5
    assert projection["stages"] == []
    assert projection["stages_deprecated"] is True
    assert len(projection["nodes"]) == 5


def test_receipts_are_not_counted_as_key_collaboration(kb):
    """「已确认收到」是送达凭据，不是推进了协作的事实。

    Regression guard: synthetic ack nodes used to carry key_action=True, so the
    default 「关键协作」 view was flooded with near-identical receipt rows and a
    newcomer could not see what actually moved.
    """
    send(kb, recipients=["@codex"], title="需求", body="提取面板")
    result = send(kb, recipients=["@human", "@research-agent"], title="初稿", body="完成",
                  sender="@codex", sender_kind="agent", record_kind="result")
    message = next(item for item in mail.iter_messages(kb, "@research-agent")
                   if item["meta"]["message_id"] == result["message_id"])
    mail.register_session(kb, "sess-ack", "research-agent")
    mail.record_delivery(kb, "sess-ack", message, agent_id="@research-agent")
    mail.acknowledge_delivery(kb, "sess-ack", result["message_id"], agent_id="@research-agent")

    projection = mail_timeline.timeline_data(kb)
    acks = [node for node in projection["nodes"] if node["action_key"] == "ack"]
    assert acks, "回执节点仍应存在，只是不占关键位"
    for node in acks:
        assert node["key_action"] is False
    # 仍然算得进「已确认收到」这个数字，也仍然能被该筛选找到。
    assert projection["counts"]["acknowledged"] >= 1
    assert projection["counts"]["primary"] == len(
        [node for node in projection["nodes"] if node["key_action"]]
    )


def test_same_instant_steps_follow_lifecycle_order(kb):
    """Steps sharing an instant read in lifecycle order, not alphabetical order.

    Regression guard: the sort key was ``(at, step)``, so ``acknowledged`` fell
    before ``presented`` and the confirmation rendered above the delivery it
    confirms — the reader sees the receipt as the cause.
    """
    stamp = "2026-09-21T10:00:00+08:00"
    rows = [{"meta": {"message_id": "m-1", "timestamp": stamp, "to": ["@codex"]},
             "title": "需求"}]
    deliveries = {
        "m-1": [{
            "agent_id": "@codex",
            "sessions": [{
                "session_id": "s-1",
                "machine_id": "mach-1",
                "injected_at": "",
                "delivered_at": stamp,
                "acknowledged_at": stamp,
            }],
        }],
    }

    steps = mail_timeline._delivery_evidence(kb, rows, deliveries)["m-1"][0]["steps"]
    assert [step["step"] for step in steps] == ["presented", "acknowledged"]


def test_ack_node_lists_each_session_once(kb):
    """The ack node's roster is a set, not a tally of steps.

    Regression guard: one Session contributes several steps (delivered, then
    acknowledged), so listing a session per step repeated the same id. The rest
    of this module already treats the roster as a set; the ack node did not.
    """
    send(kb, recipients=["@human", "@research-agent"], title="初稿", body="完成",
         sender="@codex", sender_kind="agent", record_kind="result")
    message = next(item for item in mail.iter_messages(kb, "@research-agent")
                   if item["meta"].get("record_kind") == "result")
    mail.register_session(kb, "sess-dup", "research-agent", machine_id="mach-dup")
    mail.record_delivery(kb, "sess-dup", message, agent_id="@research-agent")
    mail.acknowledge_delivery(kb, "sess-dup", message["meta"]["message_id"],
                              agent_id="@research-agent")

    ack = next(node for node in mail_timeline.timeline_data(kb)["nodes"]
               if node["action_key"] == "ack")
    assert ack["sessions"] == ["sess-dup"]
    # The Session is stamped with the machine from the fixture environment, and
    # it must appear once even though two steps (delivered + acknowledged) carry it.
    assert ack["machines"] == ["timeline-test-machine"]

