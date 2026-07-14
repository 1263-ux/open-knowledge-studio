import importlib.util
import json
import zipfile
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).parents[1] / "raw_bundle_adapter.py"
SPEC = importlib.util.spec_from_file_location("raw_bundle_adapter", MODULE_PATH)
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


def test_package_mineru_preserves_page_bbox_and_assets(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"fake-pdf")
    result = tmp_path / "mineru" / "source" / "ocr"
    images = result / "images"
    images.mkdir(parents=True)
    (images / "formula.jpg").write_bytes(b"image")
    (result / "source.md").write_text(
        "# 标题\n\n![](images/formula.jpg)\n", encoding="utf-8"
    )
    (result / "source_content_list.json").write_text(
        json.dumps(
            [
                {
                    "type": "text",
                    "text": "第一条证据",
                    "page_idx": 0,
                    "bbox": [1, 2, 3, 4],
                },
                {
                    "type": "image",
                    "img_path": "images/formula.jpg",
                    "page_idx": 1,
                    "bbox": [5, 6, 7, 8],
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "bundle"

    adapter.package_mineru(
        Namespace(
            result_dir=result.parent.parent,
            source=source,
            output=output,
            title="测试文档",
            extractor_version="3.4.4",
            warning=[],
            benchmark=True,
            overwrite=False,
        )
    )

    document = (output / "document.md").read_text(encoding="utf-8")
    assert "assets/images/formula.jpg" in document
    assert (output / "assets" / "images" / "formula.jpg").is_file()

    evidence = [
        json.loads(line)
        for line in (output / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert evidence[0]["locator"] == {"page": 1, "bbox": [1, 2, 3, 4]}
    assert evidence[1]["locator"]["asset"] == "assets/images/formula.jpg"

    quality = json.loads((output / "quality-report.json").read_text(encoding="utf-8"))
    assert quality["page_count"] == 2
    assert quality["evidence_count"] == 2
    assert quality["unresolved_asset_references"] == 0
    assert quality["processing_status"] == "partial"
    assert quality["coverage_status"] == "passed"


def test_route_plan_selects_mature_extractors():
    assert adapter.route_plan("lesson.mp4")["extractor"] == "watch"
    assert adapter.route_plan("slides.pptx")["extractor"] == "markitdown"
    assert adapter.route_plan("paper.pdf")["extractor"] == "mineru"
    assert adapter.route_plan("screenshot.png")["extractor"] == "rapidocr"
    assert "implementation_status" not in adapter.route_plan("screenshot.png")
    url_plan = adapter.route_plan("https://www.bilibili.com/video/BV123")
    assert url_plan["extractor"] == "watch"
    assert url_plan["route"][0] == "platform_caption"


def test_package_markitdown_preserves_slides_media_and_unresolved_refs(tmp_path):
    source = tmp_path / "deck.pptx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("ppt/media/image1.png", b"png")
    markdown = tmp_path / "deck.md"
    markdown.write_text(
        "<!-- Slide number: 1 -->\n\n![cover](Image0.jpg)\n第一张\n\n"
        "<!-- Slide number: 2 -->\n\n第二张\n",
        encoding="utf-8",
    )
    output = tmp_path / "bundle"

    adapter.package_markitdown(
        Namespace(
            source=source,
            markdown=markdown,
            output=output,
            title="测试演示",
            extractor_version="0.1.6",
            warning=[],
            benchmark=True,
            overwrite=False,
        )
    )

    assert (output / "assets" / "original" / "deck.pptx").is_file()
    assert (output / "assets" / "ppt-media" / "image1.png").is_file()
    assert "![cover](Image0.jpg)" in (output / "extractor-output.md").read_text(
        encoding="utf-8"
    )
    assert "未映射图片引用" in (output / "document.md").read_text(encoding="utf-8")
    evidence = [
        json.loads(line)
        for line in (output / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [item["locator"]["slide"] for item in evidence] == [1, 2]
    quality = json.loads((output / "quality-report.json").read_text(encoding="utf-8"))
    assert quality["embedded_media_count"] == 1
    assert quality["unresolved_asset_references"] == 1
    assert quality["coverage_status"] == "partial"
    assert adapter.validate_bundle(output)["valid"] is True


def test_package_watch_payload_keeps_timestamps_ocr_bbox_and_frames(tmp_path):
    source = tmp_path / "lesson.mp4"
    source.write_bytes(b"video")
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"jpeg")
    payload = {
        "acquisition": {
            "source": str(source),
            "kind": "local",
            "video_path": str(source),
            "subtitle_path": None,
            "info": {"title": "课程", "uploader": "老师"},
            "from_cache": False,
            "acquirer": "local",
        },
        "metadata": {
            "duration_seconds": 12.0,
            "width": 1920,
            "height": 1080,
            "fps": 30.0,
            "codec": "h264",
            "has_audio": True,
            "size_bytes": 5,
        },
        "transcript": {
            "source": "whisper-local (small)",
            "segments": [{"start": 1.2, "end": 3.4, "text": "三元运算符"}],
        },
        "perception": {
            "source": str(source),
            "engine": "scene",
            "scene_count": 1,
            "candidate_count": 3,
            "deduped_count": 2,
            "focused": False,
            "start_seconds": None,
            "end_seconds": None,
            "frames": [
                {
                    "index": 0,
                    "timestamp_seconds": 2.0,
                    "path": str(frame),
                    "scene_id": 0,
                    "phash": "abc",
                    "reason": "scene-mid",
                    "ocr_blocks": [
                        {
                            "text": "条件 ? 真值 : 假值",
                            "bbox": [1, 2, 30, 40],
                            "confidence": 0.93,
                        }
                    ],
                }
            ],
        },
        "start_seconds": None,
        "end_seconds": None,
    }
    output = tmp_path / "bundle"

    adapter.package_watch_payload(
        payload,
        source=str(source),
        source_file=None,
        output_path=output,
        title=None,
        extractor_version="1.0.0",
        warnings=[],
        benchmark=True,
        overwrite=False,
    )

    evidence = [
        json.loads(line)
        for line in (output / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    speech = next(item for item in evidence if item["kind"] == "speech")
    ocr = next(item for item in evidence if item["kind"] == "ocr")
    assert speech["locator"] == {"start": 1.2, "end": 3.4}
    assert ocr["locator"]["bbox"] == [1, 2, 30, 40]
    assert (output / ocr["locator"]["asset"]).is_file()
    content = (output / "content.md").read_text(encoding="utf-8")
    assert "三元运算符" in content
    assert "watch-speech-000001" in content
    assert "watch-frame-000001" in content
    assert adapter.validate_bundle(output)["valid"] is True


def test_group_transcript_and_visual_dedupe_are_readability_only():
    groups = adapter.group_transcript_segments(
        [
            {"start": 0.0, "end": 1.0, "text": "第一句"},
            {"start": 1.1, "end": 2.0, "text": "第二句"},
            {"start": 5.0, "end": 6.0, "text": "第三句"},
        ]
    )
    assert len(groups) == 2
    assert groups[0]["evidence_ids"] == [
        "watch-speech-000001",
        "watch-speech-000002",
    ]
    assert groups[0]["text"] == "第一句 第二句"
    frames = [
        {"ocr_blocks": [{"text": "相同屏幕内容"}]},
        {"ocr_blocks": [{"text": "相同屏幕内容"}]},
        {"ocr_blocks": [{"text": "新的屏幕内容"}]},
    ]
    selected = adapter.select_visual_summaries(frames)
    assert len(selected) == 2


def test_validate_bundle_reports_broken_evidence_asset(tmp_path):
    bundle = tmp_path / "broken"
    bundle.mkdir()
    (bundle / "raw.md").write_text("# Raw\n", encoding="utf-8")
    (bundle / "metadata.json").write_text(
        json.dumps(
            {
                "schema_version": adapter.SCHEMA_VERSION,
                "processing_status": "partial",
            }
        ),
        encoding="utf-8",
    )
    (bundle / "quality-report.json").write_text(
        json.dumps(
            {
                "evidence_count": 1,
                "coverage_status": "passed",
                "coverage_checks": {
                    "evidence_records": {
                        "expected": 1,
                        "observed": 1,
                        "status": "passed",
                    }
                },
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )
    (bundle / "evidence.jsonl").write_text(
        json.dumps(
            {
                "kind": "video_frame",
                "method": "test",
                "locator": {"asset": "assets/missing.jpg"},
            }
        ),
        encoding="utf-8",
    )
    report = adapter.validate_bundle(bundle)
    assert report["valid"] is False
    assert any("不存在资产" in error for error in report["errors"])


def test_url_identity_separates_url_and_content_hash(tmp_path):
    acquired = tmp_path / "downloaded.mp4"
    acquired.write_bytes(b"real-media")
    url = "https://www.bilibili.com/video/BV123"

    unavailable = adapter.source_identity(url)
    verified = adapter.source_identity(url, content_file=acquired)

    assert unavailable["content_sha256"] is None
    assert unavailable["content_hash_status"] == "unavailable"
    assert unavailable["source_url_sha256"]
    assert verified["content_hash_status"] == "verified"
    assert verified["content_sha256"] == adapter.sha256_file(acquired)
    assert verified["source_url_sha256"] == unavailable["source_url_sha256"]


def test_package_image_result_preserves_ocr_bbox_and_original(tmp_path):
    source = tmp_path / "screen.png"
    source.write_bytes(b"png")
    result = SimpleNamespace(
        txts=("知识复利", "低置信度"),
        boxes=(
            [[1, 2], [11, 2], [11, 12], [1, 12]],
            [[20, 30], [40, 30], [40, 50], [20, 50]],
        ),
        scores=(0.98, 0.2),
    )
    output = tmp_path / "image-bundle"
    args = Namespace(
        source=source,
        output=output,
        title="截图",
        extractor_version="3.4.2",
        min_confidence=0.5,
        warning=[],
        benchmark=True,
        overwrite=False,
    )

    adapter.package_image_result(args, result, elapsed_seconds=0.1)

    content = (output / "content.md").read_text(encoding="utf-8")
    assert "知识复利" in content
    assert "低置信度" not in content
    evidence = [
        json.loads(line)
        for line in (output / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert evidence[1]["locator"]["bbox"] == [1.0, 2.0, 11.0, 12.0]
    assert (output / evidence[0]["locator"]["asset"]).is_file()
    quality = json.loads((output / "quality-report.json").read_text(encoding="utf-8"))
    assert quality["coverage_status"] == "partial"
    assert quality["rejected_ocr_block_count"] == 1
    assert adapter.validate_bundle(output)["valid"] is True
