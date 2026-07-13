import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import media_ingest  # noqa: E402


class MediaIngestTests(unittest.TestCase):
    def test_slugify_keeps_chinese_and_normalizes_spaces(self):
        self.assertEqual(media_ingest.slugify("口播 知识：测试"), "口播-知识-测试")

    def test_periodic_frame_times_has_start_and_end_evidence(self):
        self.assertEqual(
            media_ingest.periodic_frame_times(65.0, 30.0),
            [5.0, 30.0, 60.0],
        )

    def test_approve_requires_explicit_human_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "raw" / "misc").mkdir(parents=True)
            with self.assertRaises(PermissionError):
                media_ingest.approve_capture(
                    root, "missing", "reviewed", confirmed=False
                )

    def test_approve_writes_raw_and_rejects_duplicate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "raw" / "misc").mkdir(parents=True)
            capture_id = "20260713-oral-abc123"
            capture = root / ".oks" / "intake" / capture_id
            (capture / "assets").mkdir(parents=True)
            metadata = {
                "capture_id": capture_id,
                "content_sha256": "a" * 64,
                "collected_date": "2026-07-13",
                "slug": "口播测试",
            }
            media_ingest.atomic_write_text(
                capture / "manifest.json",
                json.dumps(metadata, ensure_ascii=False),
            )
            media_ingest.atomic_write_text(
                capture / "candidate.md",
                '---\ncontent_sha256: "' + "a" * 64 + '"\nreview_status: pending\n---\n\n[frame](assets/a.jpg)\n',
            )
            media_ingest.atomic_write_text(
                capture / "quality-report.md", "# reviewed candidate\n"
            )
            media_ingest.atomic_write_bytes(capture / "assets" / "a.jpg", b"image")

            destination = media_ingest.approve_capture(
                root, capture_id, "checked", confirmed=True
            )

            content = destination.read_text(encoding="utf-8")
            self.assertIn("review_status: approved", content)
            self.assertIn(f"assets/{capture_id}/a.jpg", content)
            self.assertTrue(
                (root / "raw" / "misc" / "assets" / capture_id / "a.jpg").is_file()
            )
            with self.assertRaises(FileExistsError):
                media_ingest.approve_capture(
                    root, capture_id, "checked again", confirmed=True
                )

    def test_path_guard_rejects_parent_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary) / "intake"
            parent.mkdir()
            with self.assertRaises(ValueError):
                media_ingest.ensure_descendant(parent, parent)
            with self.assertRaises(ValueError):
                media_ingest.ensure_descendant(parent.parent / "elsewhere", parent)


if __name__ == "__main__":
    unittest.main()
