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
