import json
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import feishu_base_worker as worker


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
    config = worker.WorkerConfig("base", "table", tmp_path / "lark.exe", tmp_path, tmp_path / "python.exe", tmp_path, lease_seconds=60)
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


def test_attachment_change_changes_capture_hash():
    original = {"内容": "https://example.com", "思考": "note", "附件": []}
    changed = {
        **original,
        "附件": [{"file_token": "file_1", "name": "diagram.png", "size": 12}],
    }
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
