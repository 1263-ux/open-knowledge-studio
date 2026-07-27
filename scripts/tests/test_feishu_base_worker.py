import json
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import feishu_base_worker as worker


def candidate_document(title="Base review Candidate"):
    return f'''---
title: "{title}"
draft_type: strategy
draft_area: computing
source_pages: []
drafted_at: "2026-07-22"
status: draft
tags: "feishu, learning-loop"
---

# 我对它的理解

飞书多维表格是本轮 POC 的入口、状态机与人工审核控制面。Worker 负责确定性状态转换，Agent 负责需要判断的 Teach-back，审核通过后才允许晋升 Wiki。
'''


def test_extract_url_from_labeled_capture():
    assert worker.extract_url("[test] https://example.com/a?b=1。") == "https://example.com/a?b=1"
    assert worker.extract_url("plain note") is None


def test_candidate_requires_pending_or_explicit_retry():
    assert worker.is_candidate({"fields": {"运行状态": "待处理", "重试": False}})
    assert worker.is_candidate({"fields": {"运行状态": ["待处理"], "重试": False}})
    assert worker.is_candidate({"fields": {"运行状态": "最终失败", "重试": True}})
    assert not worker.is_candidate({"fields": {"运行状态": "Raw就绪", "重试": False}})


def test_expired_lease_can_be_reclaimed_but_active_lease_cannot():
    now = worker.datetime(2026, 7, 19, 12, 0, 0)
    expired = {"fields": {"运行状态": "已领取", "重试": False, "租约到期": "2026-07-19 11:59:59"}}
    active = {"fields": {"运行状态": "已领取", "重试": False, "租约到期": "2026-07-19 12:00:01"}}
    assert worker.is_candidate(expired, now=now)
    assert not worker.is_candidate(active, now=now)


def test_claim_next_record_writes_visible_lease(monkeypatch, tmp_path):
    config = worker.WorkerConfig(
        "base", "table", tmp_path / "lark.exe", tmp_path, lease_seconds=60
    )
    record = {"record_id": "rec_lease", "fields": {"运行状态": "待处理", "重试": False}}
    updates = []
    monkeypatch.setattr(worker, "list_records", lambda *_: [record])
    monkeypatch.setattr(worker, "update_record", lambda _c, record_id, patch: updates.append((record_id, patch)) or {})
    monkeypatch.setattr(worker, "local_claim_lock", lambda _config: worker.contextmanager(lambda: (yield))())

    claimed = worker.claim_next_record(config)

    assert claimed is not None
    assert claimed[0] == record
    assert claimed[1].startswith("run-")
    assert updates[0][0] == "rec_lease"
    assert updates[0][1]["运行状态"] == "已领取"
    assert updates[0][1]["租约所有者"]
    assert updates[0][1]["租约到期"]


def test_claim_record_only_reads_and_claims_the_explicit_record(monkeypatch, tmp_path):
    config = worker.WorkerConfig(
        "base",
        "table",
        tmp_path / "lark.exe",
        tmp_path,
        lease_seconds=60,
    )
    requested = []
    updates = []
    monkeypatch.setattr(
        worker,
        "get_record",
        lambda _config, record_id, projection: requested.append((record_id, projection))
        or {"record_id": record_id, "fields": {"运行状态": "待处理", "重试": False}},
    )
    monkeypatch.setattr(
        worker,
        "update_record",
        lambda _config, record_id, patch: updates.append((record_id, patch)) or {},
    )
    monkeypatch.setattr(
        worker,
        "local_claim_lock",
        lambda _config: worker.contextmanager(lambda: (yield))(),
    )

    claimed = worker.claim_record(config, "rec_selected")

    assert claimed is not None
    assert requested == [("rec_selected", worker.CAPTURE_FIELDS)]
    assert updates[0][0] == "rec_selected"
    assert updates[0][1]["运行状态"] == "已领取"


def test_attachment_change_changes_capture_hash():
    original = {"内容": "https://example.com", "思考": "note", "附件": []}
    changed = {
        **original,
        "附件": [{"file_token": "file_1", "name": "diagram.png", "size": 12}],
    }
    assert worker.capture_content_hash(original) != worker.capture_content_hash(changed)


def test_question_is_preserved_in_user_note_and_capture_hash():
    original = {
        "内容": "https://example.com",
        "思考": "值得学习",
        "希望解决的问题": "先学什么？",
    }
    changed = {**original, "希望解决的问题": "学完能做什么？"}

    assert worker.capture_user_note(original) == "值得学习\n\n希望解决的问题：先学什么？"
    assert worker.capture_content_hash(original) != worker.capture_content_hash(changed)


def test_downloaded_attachment_sha_changes_final_envelope_hash(tmp_path):
    fields = {
        "内容": "attachment only",
        "思考": "note",
        "附件": [{"file_token": "file_1", "name": "sample.txt", "size": 3}],
    }
    config = worker.WorkerConfig("base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path)
    capture = worker.capture_envelope(config, "rec_1", fields)
    before = capture["content_hash"]
    capture["attachments"][0]["sha256"] = "a" * 64
    assert worker.envelope_content_hash(capture) != before


def test_attachment_capability_routes_existing_adapters():
    assert worker.attachment_capability(Path("paper.pdf")) == ("pdf.mineru", "text")
    assert worker.attachment_capability(Path("scan.png")) == ("image.rapidocr", "ocr")
    assert worker.attachment_capability(Path("notes.txt")) == ("office.markitdown", "text")


def test_content_type_extension_supports_direct_pdf_without_url_suffix():
    assert worker.content_type_extension("application/pdf") == ".pdf"
    assert worker.content_type_extension("application/pdf; charset=binary") == ".pdf"
    assert worker.content_type_extension("application/x-unknown") == ""


def test_source_snapshot_changes_final_envelope_hash(tmp_path):
    config = worker.WorkerConfig("base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path)
    capture = worker.capture_envelope(config, "rec_1", {"内容": "https://example.com/paper.pdf", "思考": "note"})
    before = capture["content_hash"]
    capture["source_snapshot"] = {
        "final_url": "https://example.com/paper.pdf",
        "content_type": "application/pdf",
        "size": 123,
        "sha256": "a" * 64,
    }
    assert worker.envelope_content_hash(capture) != before


def test_attachment_download_passes_repository_relative_output(monkeypatch, tmp_path):
    output = worker.ROOT / ".oks" / "runs" / "test-relative-output"
    config = worker.WorkerConfig("base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path)
    commands = []
    monkeypatch.setattr(worker, "lark_json", lambda _config, *args: commands.append(args) or {})
    worker.download_attachments(config, "rec_1", output)
    output_arg = commands[0][commands[0].index("--output") + 1]
    assert output_arg == "./.oks/runs/test-relative-output"


def test_list_records_maps_projected_rows(monkeypatch, tmp_path):
    config = worker.WorkerConfig("base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path)
    monkeypatch.setattr(
        worker,
        "lark_json",
        lambda *_args: {
            "data": {
                "fields": ["内容", "运行状态", "重试"],
                "data": [["https://example.com", "待处理", False]],
                "record_id_list": ["rec_1"],
            }
        },
    )
    assert worker.list_records(config) == [
        {
            "record_id": "rec_1",
            "fields": {"内容": "https://example.com", "运行状态": "待处理", "重试": False},
        }
    ]


def test_publish_candidate_requires_raw_and_writes_visible_review_state(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    raw = tmp_path / "raw-bundle"
    raw.mkdir()
    (raw / "bundle.json").write_text(
        json.dumps(
            {
                "schema_version": "raw-multimodal/v0.2",
                "capture_id": "capture_1",
                "bundle_id": "bundle:capture_1:run_1",
            }
        ),
        encoding="utf-8",
    )
    source = tmp_path / "base-review-candidate.md"
    source.write_text(candidate_document(), encoding="utf-8")
    config = worker.WorkerConfig("base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path)
    updates = []
    monkeypatch.setattr(
        worker,
        "get_record",
        lambda *_: {
            "record_id": "rec_1",
            "fields": {"运行状态": "Raw就绪", "Raw Bundle": str(raw), "运行ID": "run_1"},
        },
    )
    monkeypatch.setattr(worker, "update_record", lambda _c, _r, patch: updates.append(patch) or {})
    notifications = []
    monkeypatch.setattr(
        worker,
        "send_candidate_review_notification",
        lambda *_args, **kwargs: notifications.append(kwargs)
        or {"status": "sent", "message_id": "om_1"},
    )

    state = worker.publish_candidate(config, "rec_1", source)

    assert state["candidate_id"] == "base-review-candidate"
    assert state["revision"] == 1
    assert (tmp_path / state["candidate_path"]).is_file()
    assert updates[-1]["候选ID"] == "base-review-candidate"
    assert updates[-1]["Wiki状态"] == "review_pending"
    assert updates[-1]["运行状态"] == "候选待审"
    assert "飞书多维表格" in updates[-1]["候选内容"]
    assert state["review_notification"]["status"] == "sent"
    assert notifications[0]["record_id"] == "rec_1"
    metadata, _body = worker.parse_candidate_document(
        (tmp_path / state["candidate_path"]).read_text(encoding="utf-8")
    )
    execution_trace = metadata["traces"][0]
    assert execution_trace == {
        "kind": "execution",
        "id": "run_1",
        "capture_id": "capture_1",
        "bundle_id": "bundle:capture_1:run_1",
        "path": "raw-bundle",
    }


def test_publish_candidate_writes_draft_to_configured_personal_root(monkeypatch, tmp_path):
    studio_root = tmp_path / "studio"
    personal_root = tmp_path / "personal"
    raw = personal_root / "raw" / "bundle"
    raw.mkdir(parents=True)
    (raw / "bundle.json").write_text(
        json.dumps({"capture_id": "capture_1", "bundle_id": "bundle_1"}),
        encoding="utf-8",
    )
    source = tmp_path / "personal-candidate.md"
    source.write_text(candidate_document(), encoding="utf-8")
    monkeypatch.setattr(worker, "ROOT", studio_root)
    config = worker.WorkerConfig(
        "base",
        "table",
        tmp_path / "lark.exe",
        tmp_path,
        tmp_path / "python.exe",
        raw.parent,
        knowledge_root=personal_root,
    )
    monkeypatch.setattr(
        worker,
        "get_record",
        lambda *_: {
            "record_id": "rec_personal",
            "fields": {"运行状态": "Raw就绪", "Raw Bundle": str(raw), "运行ID": "run_1"},
        },
    )
    monkeypatch.setattr(worker, "update_record", lambda *_: {})
    monkeypatch.setattr(
        worker,
        "send_candidate_review_notification",
        lambda *_args, **_kwargs: {"status": "disabled"},
    )

    state = worker.publish_candidate(config, "rec_personal", source)

    candidate = personal_root / "drafts" / "personal-candidate.md"
    assert candidate.is_file()
    assert state["candidate_path"] == str(candidate)
    assert Path(state["candidate_path"]).is_absolute()


def test_promote_candidate_document_uses_configured_personal_root(monkeypatch, tmp_path):
    studio_root = tmp_path / "studio"
    personal_root = tmp_path / "personal"
    candidate = personal_root / "drafts" / "personal-candidate.md"
    candidate.parent.mkdir(parents=True)
    candidate.write_text(candidate_document(), encoding="utf-8")
    monkeypatch.setattr(worker, "ROOT", studio_root)
    monkeypatch.setenv("OKS_ROOT", str(studio_root))

    wiki_path = worker.promote_candidate_document(
        candidate,
        worker.parse_candidate_document(candidate.read_text(encoding="utf-8"))[1],
        {
            "outcome": "success",
            "decision_correct": True,
            "lesson": "验收通过",
            "reviewed_at": "2026-07-24 12:00:00",
        },
        knowledge_root=personal_root,
    )

    assert wiki_path.is_relative_to(personal_root / "wiki")
    assert wiki_path.is_file()
    assert not (studio_root / "wiki").exists()
    assert worker.os.environ["OKS_ROOT"] == str(studio_root)


def test_render_candidate_review_message_uses_agent_summary_and_questions():
    message = worker.render_candidate_review_message(
        record_id="rec_1",
        candidate_id="candidate-1",
        revision=2,
        metadata={
            "title": "控制面设计",
            "review_summary": "Base 保存审计事实，Agent 负责解释与提问。",
            "review_questions": ["这条知识是否值得保留？", "是否需要补充反例？"],
        },
        body="完整 Candidate 正文。" * 20,
        fields={"内容": "https://example.com", "思考": "如何降低审核摩擦？"},
    )

    assert "控制面设计" in message
    assert "Base 保存审计事实" in message
    assert "这条知识是否值得保留" in message
    assert "如何降低审核摩擦" in message
    assert "candidate-1" in message
    assert "revision `2`" in message


def test_review_notification_skips_without_configured_recipient(tmp_path):
    config = worker.WorkerConfig(
        "base",
        "table",
        tmp_path / "lark.exe",
        tmp_path,
        tmp_path / "python.exe",
        tmp_path,
    )

    result = worker.send_candidate_review_notification(
        config,
        record_id="rec_1",
        state={
            "candidate_id": "candidate-1",
            "revision": 1,
            "candidate_sha256": "a" * 64,
        },
        metadata={"title": "Candidate"},
        body="正文" * 50,
        fields={},
    )

    assert result == {"status": "skipped", "reason": "review_recipient_not_configured"}


def test_review_notification_sends_idempotent_personal_message(monkeypatch, tmp_path):
    config = worker.WorkerConfig(
        "base",
        "table",
        tmp_path / "lark.exe",
        tmp_path,
        tmp_path / "python.exe",
        tmp_path,
        review_recipient_user_id="ou_user",
        review_message_identity="bot",
    )
    commands = []
    monkeypatch.setattr(
        worker,
        "lark_json",
        lambda _config, *args: commands.append(args)
        or {"data": {"message_id": "om_1"}},
    )

    result = worker.send_candidate_review_notification(
        config,
        record_id="rec_1",
        state={
            "candidate_id": "candidate-1",
            "revision": 1,
            "candidate_sha256": "a" * 64,
        },
        metadata={"title": "Candidate", "review_summary": "摘要"},
        body="正文" * 50,
        fields={},
    )

    assert result["status"] == "sent"
    assert result["message_id"] == "om_1"
    assert commands[0][:2] == ("im", "+messages-send")
    assert commands[0][commands[0].index("--user-id") + 1] == "ou_user"
    assert commands[0][commands[0].index("--as") + 1] == "bot"
    assert len(commands[0][commands[0].index("--idempotency-key") + 1]) == 50


def test_parse_review_reply_accepts_action_before_or_after_comment():
    assert worker.parse_review_reply("accept 文章有价值") == ("accept", "文章有价值")
    assert worker.parse_review_reply("文章有价值，accept") == ("accept", "文章有价值")
    assert worker.parse_review_reply("`defer`") == ("defer", "")


def test_parse_review_reply_rejects_missing_or_conflicting_action():
    for content in ("文章有价值", "accept but reject"):
        try:
            worker.parse_review_reply(content)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid review reply accepted: {content}")


def test_personal_reply_updates_exact_linked_candidate_and_records_receipt(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    state_path = worker.candidate_state_path("rec_reply")
    worker.atomic_write_json(
        state_path,
        {
            "record_id": "rec_reply",
            "candidate_id": "candidate-1",
            "revision": 3,
            "review_notification": {
                "status": "sent",
                "message_id": "om_prompt",
                "chat_id": "oc_personal",
                "recipient": "ou_reviewer",
            },
        },
    )
    config = worker.WorkerConfig(
        "base",
        "table",
        tmp_path / "lark.exe",
        tmp_path,
        tmp_path / "python.exe",
        tmp_path,
        review_recipient_user_id="ou_reviewer",
    )
    updates = []
    monkeypatch.setattr(
        worker,
        "update_record",
        lambda _config, record_id, patch: updates.append((record_id, patch)) or {},
    )
    monkeypatch.setattr(
        worker,
        "get_record",
        lambda _config, record_id: {
            "record_id": record_id,
            "fields": {"审核动作": "accept"},
        },
    )
    monkeypatch.setattr(
        worker,
        "review_candidate",
        lambda _config, record: {
            "processed": True,
            "record_id": record["record_id"],
            "action": "accept",
        },
    )
    event = {
        "event_id": "evt_1",
        "message_id": "om_reply",
        "reply_to": "om_prompt",
        "root_id": "om_prompt",
        "chat_id": "oc_personal",
        "chat_type": "p2p",
        "sender_id": "ou_reviewer",
        "sender_type": "user",
        "message_type": "text",
        "content": "文章有价值，accept",
        "create_time": "1784730000000",
    }

    first = worker.apply_review_reply_event(config, event)
    second = worker.apply_review_reply_event(config, event)

    assert first["processed"] is True
    assert first["record_id"] == "rec_reply"
    assert first["revision"] == 3
    assert updates[0][0] == "rec_reply"
    assert updates[0][1]["审核动作"] == "accept"
    assert updates[0][1]["审核意见"] == "文章有价值"
    assert updates[0][1]["修改类型"] == ["无修改"]
    assert second["reason"] == "review_message_already_processed"
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["review_reply_events"][0]["message_id"] == "om_reply"


def test_review_reply_requires_exact_parent_and_comment_for_reject(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    worker.atomic_write_json(
        worker.candidate_state_path("rec_reply"),
        {
            "record_id": "rec_reply",
            "candidate_id": "candidate-1",
            "revision": 1,
            "review_notification": {
                "status": "sent",
                "message_id": "om_prompt",
                "chat_id": "oc_personal",
                "recipient": "ou_reviewer",
            },
        },
    )
    config = worker.WorkerConfig(
        "base",
        "table",
        tmp_path / "lark.exe",
        tmp_path,
        tmp_path / "python.exe",
        tmp_path,
    )
    base_event = {
        "message_id": "om_reply",
        "reply_to": "om_prompt",
        "chat_id": "oc_personal",
        "chat_type": "p2p",
        "sender_id": "ou_reviewer",
        "sender_type": "user",
        "message_type": "text",
        "content": "reject",
    }
    assert worker.apply_review_reply_event(config, base_event)["reason"] == "review_comment_required"
    assert worker.apply_review_reply_event(
        config,
        {**base_event, "reply_to": "om_other", "content": "reject 方向偏离"},
    )["reason"] == "unknown_review_notification"


def test_reconcile_historical_review_uses_strict_p2p_sequence_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    worker.atomic_write_json(
        worker.candidate_state_path("rec_reply"),
        {
            "record_id": "rec_reply",
            "candidate_id": "candidate-1",
            "revision": 1,
            "review_notification": {
                "status": "sent",
                "message_id": "om_prompt",
                "chat_id": "oc_personal",
                "recipient": "ou_reviewer",
            },
        },
    )
    messages = {
        "om_prompt": {
            "message_id": "om_prompt",
            "chat_id": "oc_personal",
            "message_position": "2",
            "create_time": "1784730000000",
        },
        "om_reply": {
            "message_id": "om_reply",
            "chat_id": "oc_personal",
            "message_position": "3",
            "create_time": "1784730001000",
            "msg_type": "text",
            "sender": {"id": "ou_reviewer", "sender_type": "user"},
            "body": {"content": json.dumps({"text": "accept, useful"})},
        },
    }
    monkeypatch.setattr(worker, "raw_message", lambda _config, message_id: messages[message_id])
    events = []
    monkeypatch.setattr(
        worker,
        "apply_review_reply_event",
        lambda _config, event: events.append(event) or {"processed": True},
    )
    config = worker.WorkerConfig(
        "base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path
    )

    result = worker.reconcile_historical_review_reply(
        config,
        prompt_message_id="om_prompt",
        reply_message_id="om_reply",
    )

    assert result["processed"] is True
    assert result["correlation_method"] == "p2p_sequence_fallback"
    assert events[0]["reply_to"] == "om_prompt"
    assert events[0]["content"] == "accept, useful"


def test_unknown_standalone_review_automatically_uses_strict_sequence_fallback(
    monkeypatch, tmp_path
):
    config = worker.WorkerConfig(
        "base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path
    )
    state = {
        "review_notification": {
            "status": "sent",
            "message_id": "om_prompt",
            "chat_id": "oc_personal",
        }
    }
    monkeypatch.setattr(
        worker,
        "apply_review_reply_event",
        lambda *_args: {
            "processed": False,
            "reason": "unknown_review_notification",
            "message_id": "om_reply",
        },
    )
    monkeypatch.setattr(
        worker,
        "pending_review_states_in_chat",
        lambda chat_id: [(tmp_path / "state.json", state)]
        if chat_id == "oc_personal"
        else [],
    )
    reconciled = []
    monkeypatch.setattr(
        worker,
        "reconcile_historical_review_reply",
        lambda _config, **kwargs: reconciled.append(kwargs)
        or {"processed": True, "correlation_method": "p2p_sequence_fallback"},
    )

    result = worker.apply_review_event_with_fallback(
        config,
        {
            "message_id": "om_reply",
            "chat_id": "oc_personal",
        },
    )

    assert result["processed"] is True
    assert reconciled == [
        {
            "prompt_message_id": "om_prompt",
            "reply_message_id": "om_reply",
        }
    ]


def test_standalone_review_fallback_does_not_guess_between_candidates(monkeypatch, tmp_path):
    config = worker.WorkerConfig(
        "base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path
    )
    monkeypatch.setattr(
        worker,
        "apply_review_reply_event",
        lambda *_args: {
            "processed": False,
            "reason": "unknown_review_notification",
            "message_id": "om_reply",
        },
    )
    monkeypatch.setattr(
        worker,
        "pending_review_states_in_chat",
        lambda _chat_id: [
            (tmp_path / "one.json", {}),
            (tmp_path / "two.json", {}),
        ],
    )

    result = worker.apply_review_event_with_fallback(
        config,
        {"message_id": "om_reply", "chat_id": "oc_personal"},
    )

    assert result["reason"] == "unknown_review_notification"


def test_review_write_read_retries_a_stale_base_snapshot(monkeypatch, tmp_path):
    config = worker.WorkerConfig(
        "base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path
    )
    records = iter(
        [
            {"record_id": "rec_reply", "fields": {"审核动作": None}},
            {"record_id": "rec_reply", "fields": {"审核动作": ["accept"]}},
        ]
    )
    delays = []
    monkeypatch.setattr(worker, "get_record", lambda *_args: next(records))
    monkeypatch.setattr(worker.time, "sleep", lambda delay: delays.append(delay))

    record = worker.read_review_record_after_write(config, "rec_reply", "accept")

    assert worker.scalar_cell(record["fields"]["审核动作"]) == "accept"
    assert delays == [0.25]


def test_reconcile_historical_review_rejects_nonadjacent_message(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    worker.atomic_write_json(
        worker.candidate_state_path("rec_reply"),
        {
            "record_id": "rec_reply",
            "review_notification": {
                "status": "sent",
                "message_id": "om_prompt",
                "chat_id": "oc_personal",
                "recipient": "ou_reviewer",
            },
        },
    )
    messages = {
        "om_prompt": {
            "message_id": "om_prompt",
            "chat_id": "oc_personal",
            "message_position": "2",
            "create_time": "1784730000000",
        },
        "om_reply": {
            "message_id": "om_reply",
            "chat_id": "oc_personal",
            "message_position": "4",
            "create_time": "1784730001000",
            "msg_type": "text",
            "sender": {"id": "ou_reviewer", "sender_type": "user"},
            "body": {"content": json.dumps({"text": "accept"})},
        },
    }
    monkeypatch.setattr(worker, "raw_message", lambda _config, message_id: messages[message_id])
    config = worker.WorkerConfig(
        "base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path
    )

    try:
        worker.reconcile_historical_review_reply(
            config,
            prompt_message_id="om_prompt",
            reply_message_id="om_reply",
        )
    except RuntimeError as error:
        assert "immediately follow" in str(error)
    else:
        raise AssertionError("A nonadjacent message must not be correlated as a review")


def test_reconcile_historical_review_is_idempotent_after_promotion(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    worker.atomic_write_json(
        worker.candidate_state_path("rec_reply"),
        {
            "record_id": "rec_reply",
            "last_review_action": "accept",
            "review_notification": {
                "status": "sent",
                "message_id": "om_prompt",
                "chat_id": "oc_personal",
                "recipient": "ou_reviewer",
            },
            "review_reply_events": [
                {
                    "message_id": "om_reply",
                    "correlation_method": "p2p_sequence_fallback",
                }
            ],
        },
    )
    messages = {
        "om_prompt": {"message_id": "om_prompt", "chat_id": "oc_personal"},
        "om_reply": {"message_id": "om_reply", "chat_id": "oc_personal"},
    }
    monkeypatch.setattr(worker, "raw_message", lambda _config, message_id: messages[message_id])
    config = worker.WorkerConfig(
        "base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path
    )

    result = worker.reconcile_historical_review_reply(
        config,
        prompt_message_id="om_prompt",
        reply_message_id="om_reply",
    )

    assert result["processed"] is False
    assert result["reason"] == "review_message_already_processed"
    assert result["correlation_method"] == "p2p_sequence_fallback"


def test_review_listener_uses_bounded_filtered_bot_event_consumer(monkeypatch, tmp_path):
    config = worker.WorkerConfig(
        "base",
        "table",
        tmp_path / "lark.exe",
        tmp_path,
        tmp_path / "python.exe",
        tmp_path,
        review_recipient_user_id="ou_reviewer",
    )
    event = {"message_id": "om_reply", "chat_type": "p2p", "sender_type": "user"}
    commands = []
    monkeypatch.setattr(
        worker.subprocess,
        "run",
        lambda command, **_kwargs: commands.append(command)
        or worker.subprocess.CompletedProcess(command, 0, json.dumps(event) + "\n", "[event] ready\n"),
    )
    monkeypatch.setattr(
        worker,
        "apply_review_reply_event",
        lambda _config, value: {"processed": True, "message_id": value["message_id"]},
    )

    result = worker.consume_review_events(config, max_events=1, timeout="30s")

    assert result["events_received"] == 1
    assert result["outcomes"][0]["processed"] is True
    assert commands[0][1:4] == ["event", "consume", "im.message.receive_v1"]
    assert commands[0][commands[0].index("--as") + 1] == "bot"
    assert commands[0][commands[0].index("--max-events") + 1] == "1"
    assert "ou_reviewer" in commands[0][commands[0].index("--jq") + 1]


def test_publish_candidate_refuses_record_without_raw(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    source = tmp_path / "candidate.md"
    source.write_text(candidate_document(), encoding="utf-8")
    config = worker.WorkerConfig("base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path)
    monkeypatch.setattr(
        worker,
        "get_record",
        lambda *_: {"record_id": "rec_1", "fields": {"运行状态": "Raw就绪", "Raw Bundle": None}},
    )

    try:
        worker.publish_candidate(config, "rec_1", source)
    except RuntimeError as error:
        assert "no Raw Bundle" in str(error)
    else:
        raise AssertionError("Candidate publication must require a Raw Bundle")


def test_reject_review_is_persistent_and_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    candidate = tmp_path / "drafts" / "base-review-candidate.md"
    candidate.parent.mkdir()
    candidate.write_text(candidate_document(), encoding="utf-8")
    worker.atomic_write_json(
        worker.candidate_state_path("rec_1"),
        {
            "candidate_id": "base-review-candidate",
            "candidate_path": "drafts/base-review-candidate.md",
            "review_history": [],
            "last_review_fingerprint": None,
        },
    )
    fields = {
        "候选ID": "base-review-candidate",
        "候选内容": "这是用户看到并拒绝的候选内容，因为它偏离了飞书 Base 主循环的真正验收目标。" * 3,
        "审核动作": "reject",
        "审核意见": "方向偏离，不晋升 Wiki。",
        "修改类型": ["方向偏离"],
        "审核时间": "2026-07-22 00:10:00",
    }
    config = worker.WorkerConfig("base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path)
    updates = []
    monkeypatch.setattr(worker, "update_record", lambda _c, _r, patch: updates.append(patch) or {})

    first = worker.review_candidate(config, {"record_id": "rec_1", "fields": fields})
    second = worker.review_candidate(config, {"record_id": "rec_1", "fields": fields})

    assert first["processed"] is True
    assert first["action"] == "reject"
    assert updates == [{
        "运行状态": "已拒绝",
        "Wiki状态": "rejected",
        "Wiki路径": None,
        "审核时间": "2026-07-22 00:10:00",
    }]
    metadata, _body = worker.parse_candidate_document(candidate.read_text(encoding="utf-8"))
    assert metadata["status"] == "rejected"
    assert metadata["review"]["lesson"] == "方向偏离，不晋升 Wiki。"
    assert second == {"processed": False, "reason": "review_already_processed", "record_id": "rec_1"}


def test_accept_review_promotes_exact_base_content(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    candidate = tmp_path / "drafts" / "base-review-candidate.md"
    candidate.parent.mkdir()
    candidate.write_text(candidate_document(), encoding="utf-8")
    worker.atomic_write_json(
        worker.candidate_state_path("rec_2"),
        {
            "candidate_id": "base-review-candidate",
            "candidate_path": "drafts/base-review-candidate.md",
            "review_history": [],
            "last_review_fingerprint": None,
        },
    )
    accepted_body = "这是用户在飞书 Base 中最终确认的 Teach-back 内容。" * 5
    fields = {
        "候选ID": "base-review-candidate",
        "候选内容": accepted_body,
        "审核动作": "accept",
        "审核意见": "验收通过。",
        "修改类型": ["无修改"],
        "审核时间": "2026-07-22 00:20:00",
    }
    wiki = tmp_path / "wiki" / "computing" / "strategies" / "accepted.md"
    wiki.parent.mkdir(parents=True)
    wiki.write_text("accepted", encoding="utf-8")
    promoted = []
    monkeypatch.setattr(
        worker,
        "promote_candidate_document",
        lambda path, body, review, **_kwargs: promoted.append((path, body, review)) or wiki,
    )
    updates = []
    monkeypatch.setattr(worker, "update_record", lambda _c, _r, patch: updates.append(patch) or {})
    config = worker.WorkerConfig("base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path)

    result = worker.review_candidate(config, {"record_id": "rec_2", "fields": fields})

    assert result["action"] == "accept"
    assert promoted[0][1] == accepted_body
    assert promoted[0][2]["lesson"] == "验收通过。"
    assert updates[-1]["运行状态"] == "已晋升"
    assert updates[-1]["Wiki状态"] == "promoted"
    assert updates[-1]["Wiki路径"] == "wiki/computing/strategies/accepted.md"
    assert updates[-1]["审核时间"] == "2026-07-22 00:20:00"


def test_needs_user_action_never_claims_raw_ready(monkeypatch, tmp_path):
    config = worker.WorkerConfig("base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path / "out")
    updates = []
    monkeypatch.setattr(worker, "update_record", lambda _c, _r, patch: updates.append(patch) or {})
    monkeypatch.setattr(
        worker,
        "probe_source",
        lambda *_: {
            "status": "needs_user_action",
            "error": {"code": "CHALLENGE_REQUIRED", "message": "captcha required"},
        },
    )
    result = worker.process_record(
        config,
        {"record_id": "rec_1", "fields": {"内容": "https://example.com", "思考": "test"}},
    )
    assert result["status"] == "failed"
    assert result["failure_disposition"] == "needs_user_auth"
    assert updates[-1]["运行状态"] == "需授权"
    assert updates[-1]["Raw Bundle"] is None
    assert all(update.get("运行状态") != "Raw就绪" for update in updates)


def test_javascript_page_waits_for_browser_snapshot(monkeypatch, tmp_path):
    config = worker.WorkerConfig("base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path / "out")
    updates = []
    monkeypatch.setattr(worker, "update_record", lambda _c, _r, patch: updates.append(patch) or {})
    monkeypatch.setattr(
        worker,
        "probe_source",
        lambda *_: {
            "status": "ok",
            "content_type": "text/html",
            "next_action": "browser_public",
            "error": {"code": "JS_RENDER_REQUIRED", "message": "render required"},
        },
    )
    monkeypatch.setattr(worker, "package_public_web", lambda *_: (_ for _ in ()).throw(AssertionError("must not package pre-render HTML")))

    result = worker.process_record(
        config,
        {"record_id": "rec_js", "fields": {"内容": "https://example.com/app", "思考": "test"}},
    )

    assert result["status"] == "failed"
    assert result["failure_disposition"] == "needs_user_action"
    assert updates[-1]["运行状态"] == "需人工"
    assert updates[-1]["采集模式"] == "公开浏览器"
    assert updates[-1]["Raw Bundle"] is None


def test_platform_route_uses_watch_and_reference_snapshot(monkeypatch, tmp_path):
    config = worker.WorkerConfig("base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path / "out")
    updates = []
    monkeypatch.setattr(worker, "update_record", lambda _c, _r, patch: updates.append(patch) or {})
    monkeypatch.setattr(
        worker,
        "probe_source",
        lambda *_: {
            "status": "ok", "content_type": "text/html", "final_url": "https://www.bilibili.com/video/BV1/",
            "next_action": "platform_extractor", "route_plan": {"platform": "bilibili", "source_type": "video"},
        },
    )
    def fake_package(_config, _source, output):
        output.mkdir(parents=True)
        (output / "metadata.json").write_text('{"processing_status":"partial"}', encoding="utf-8")
        (output / "quality-report.json").write_text('{"processing_status":"partial","frame_count":1,"transcript_segment_count":0,"ocr_block_count":2,"warnings":[]}', encoding="utf-8")
        return {"processing_status": "partial"}
    finalized = []
    monkeypatch.setattr(worker, "package_routed_source", fake_package)
    monkeypatch.setattr(worker, "finalize_raw_v2", lambda *_args: finalized.append(_args) or {"valid": True})

    result = worker.process_record(config, {"record_id": "rec_video", "fields": {"内容": "https://www.bilibili.com/video/BV1", "思考": "test"}})

    assert result["status"] == "partial"
    assert result["job"]["capability"] == "video.watch"
    assert result["modalities"]["video"]["evidence_count"] == 1
    assert result["modalities"]["ocr"]["evidence_count"] == 2
    assert updates[-1]["运行状态"] == "Raw就绪"
    assert updates[-1]["采集模式"] == "平台提取器"
    reference = finalized[0][-1]
    assert json.loads(reference.read_text(encoding="utf-8"))["original_media_retained"] is False


def test_platform_failure_is_attributed_to_video_modality(monkeypatch, tmp_path):
    config = worker.WorkerConfig("base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path / "out")
    updates = []
    monkeypatch.setattr(worker, "update_record", lambda _c, _r, patch: updates.append(patch) or {})
    monkeypatch.setattr(
        worker,
        "probe_source",
        lambda *_: {
            "status": "ok", "content_type": "text/html", "final_url": "https://www.bilibili.com/video/BV1/",
            "next_action": "platform_extractor", "route_plan": {"platform": "bilibili", "source_type": "video"},
        },
    )
    monkeypatch.setattr(worker, "package_routed_source", lambda *_: (_ for _ in ()).throw(RuntimeError("HTTP 412")))

    result = worker.process_record(config, {"record_id": "rec_video_fail", "fields": {"内容": "https://www.bilibili.com/video/BV1", "思考": "test"}})

    assert result["status"] == "failed"
    assert result["modalities"]["video"]["status"] == "failed"
    assert result["modalities"]["video"]["error_code"] == "PLATFORM_EXTRACTOR_FAILED"
    assert result["modalities"]["text"]["status"] == "skipped"
    assert result["errors"][0]["modality"] == "video"
    assert updates[-1]["运行状态"] == "可重试失败"
