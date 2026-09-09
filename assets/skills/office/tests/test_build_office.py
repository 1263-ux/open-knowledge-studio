from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_office.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("build_office", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


VALID = {
    "title": "Smoke",
    "summary": "A sourced summary.",
    "summary_source_refs": ["source-1"],
    "sections": [
        {
            "heading": "Claims",
            "source_refs": ["source-1"],
            "paragraphs": ["A paragraph"],
            "bullets": [{"text": "A bullet", "source_refs": ["source-1"]}],
            "table": [["Metric", "Value"], ["Count", 0], ["Enabled", False]],
        }
    ],
    "sources": [
        {"id": "source-1", "label": "Wiki", "path": "wiki/example.md", "status": "reviewed"}
    ],
}


class OfficeOutlineTests(unittest.TestCase):
    def load(self, outline):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "outline.json"
            path.write_text(json.dumps(outline), encoding="utf-8")
            return MODULE.load_outline(path)

    def test_source_refs_are_required(self):
        outline = copy.deepcopy(VALID)
        del outline["sections"][0]["source_refs"]
        with self.assertRaisesRegex(ValueError, "source_refs"):
            self.load(outline)

    def test_source_entries_are_strict(self):
        outline = copy.deepcopy(VALID)
        outline["sources"][0]["path"] = ""
        with self.assertRaisesRegex(ValueError, "requires id, label, and path"):
            self.load(outline)

    def test_zero_and_false_are_preserved(self):
        self.assertEqual(MODULE.text(0), "0")
        self.assertEqual(MODULE.text(False), "False")

    def test_irregular_tables_are_rejected(self):
        outline = copy.deepcopy(VALID)
        outline["sections"][0]["table"].append(["too", "many", "cells"])
        with self.assertRaisesRegex(ValueError, "rectangular"):
            self.load(outline)

        outline["sections"][0]["table"] = {}
        with self.assertRaisesRegex(ValueError, "table must be a list"):
            self.load(outline)

    def test_cjk_pdf_requires_font(self):
        outline = copy.deepcopy(VALID)
        outline["title"] = "中文标题"
        self.load(outline)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "CJK content requires"):
                MODULE.render_pdf(outline, Path(directory) / "out.pdf", None)

    def test_slide_chunking_does_not_drop_text(self):
        value = "0123456789" * 100
        self.assertEqual("".join(MODULE.split_for_slide(value)), value)

    def test_source_line_keeps_external_research_url_and_retrieval_time(self):
        line = MODULE.source_line(
            {
                "id": "web-1",
                "kind": "research",
                "label": "Research: issuer",
                "path": "https://example.com/report",
                "retrieved_at": "2026-08-27T10:00:00+08:00",
                "status": "unverified",
            }
        )
        self.assertIn("https://example.com/report", line)
        self.assertIn("research", line)
        self.assertIn("retrieved 2026-08-27T10:00:00+08:00", line)


if __name__ == "__main__":
    unittest.main()
