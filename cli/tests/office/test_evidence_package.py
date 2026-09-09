from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).parents[3]
SCRIPT = ROOT / "assets" / "skills" / "office" / "scripts" / "evidence_package.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("evidence_package", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

VALID = {
    "schema_version": "oks-office-evidence/v1",
    "request": {"title": "中文申报书", "audience": "评审专家", "deliverables": ["docx", "pdf", "pptx"]},
    "recall": {"query": "agent 技术", "items": [{"slug": "agent-page", "score": 0.9}]},
    "summary": {"text": "证据边界内的摘要。", "claim_refs": ["claim-1"]},
    "claims": [
        {
            "id": "claim-1",
            "text": "系统支持可追溯输出。",
            "source_refs": ["src-1"],
            "confidence": "high",
            "review_status": "reviewed",
        },
        {
            "id": "claim-2",
            "text": "指标为 0，开关为 False。",
            "source_refs": ["src-1"],
            "confidence": "medium",
            "review_status": "provisional",
        },
    ],
    "sections": [
        {
            "id": "section-1",
            "title": "能力",
            "claim_refs": ["claim-1", "claim-2"],
            "blocks": [
                {"type": "paragraph", "text": "能力说明。", "claim_refs": ["claim-1"]},
                {
                    "type": "bullets",
                    "items": [{"text": "证据链保留。", "claim_refs": ["claim-1"]}, "指标保真。"],
                    "claim_refs": ["claim-1", "claim-2"],
                },
                {"type": "table", "rows": [["字段", "值"], ["count", 0], ["enabled", False]], "claim_refs": ["claim-2"]},
            ],
        }
    ],
    "sources": [
        {"id": "src-1", "kind": "wiki", "label": "Wiki: agent-page", "locator": "wiki/agent.md", "status": "reviewed"},
        {
            "id": "src-research-1",
            "kind": "research",
            "label": "Research: primary source",
            "locator": "https://example.com/source",
            "retrieved_at": "2026-08-27T10:00:00+08:00",
            "status": "unverified",
        },
    ],
}


class EvidencePackageTests(unittest.TestCase):
    def test_fixed_research_requires_an_external_source_record(self):
        package = copy.deepcopy(VALID)
        package["sources"] = [package["sources"][0]]
        with self.assertRaisesRegex(ValueError, "fixed research step"):
            MODULE.validate_package(package)

    def test_fixed_recall_requires_a_recorded_query(self):
        package = copy.deepcopy(VALID)
        del package["recall"]
        with self.assertRaisesRegex(ValueError, "recall.query"):
            MODULE.validate_package(package)

    def test_direct_external_research_cannot_be_labeled_reviewed(self):
        package = copy.deepcopy(VALID)
        package["sources"][1]["status"] = "reviewed"
        with self.assertRaisesRegex(ValueError, "cannot be reviewed"):
            MODULE.validate_package(package)

        package = copy.deepcopy(VALID)
        package["claims"][0]["source_refs"] = ["src-research-1"]
        with self.assertRaisesRegex(ValueError, "cannot be reviewed"):
            MODULE.validate_package(package)

    def test_external_research_timestamp_must_be_timezone_aware_iso_8601(self):
        package = copy.deepcopy(VALID)
        package["sources"][1]["retrieved_at"] = "not-a-timestamp"
        with self.assertRaisesRegex(ValueError, "ISO 8601"):
            MODULE.validate_package(package)

    def test_claim_sources_are_required_and_known(self):
        package = copy.deepcopy(VALID)
        del package["claims"][0]["source_refs"]
        with self.assertRaisesRegex(ValueError, "source_refs"):
            MODULE.validate_package(package)

        package = copy.deepcopy(VALID)
        package["claims"][0]["source_refs"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "unknown ids"):
            MODULE.validate_package(package)

    def test_external_research_requires_url_and_retrieval_time(self):
        package = copy.deepcopy(VALID)
        package["sources"][0] = {
            "id": "src-1",
            "kind": "research",
            "label": "Research: example",
            "locator": "records/research/example.md",
            "status": "unverified",
        }
        with self.assertRaisesRegex(ValueError, "http\\(s\\) URL"):
            MODULE.validate_package(package)

        package["sources"][0]["locator"] = "https://example.com/report"
        with self.assertRaisesRegex(ValueError, "retrieved_at"):
            MODULE.validate_package(package)

        package["sources"][0]["retrieved_at"] = "2026-08-27T10:00:00+08:00"
        package["claims"][0]["review_status"] = "provisional"
        MODULE.validate_package(package)

    def test_unknown_source_kind_fails_closed(self):
        package = copy.deepcopy(VALID)
        package["sources"][0]["kind"] = "search_snippet"
        with self.assertRaisesRegex(ValueError, "kind must be one of"):
            MODULE.validate_package(package)

    def test_external_research_fixture_is_provisional_and_traceable(self):
        fixture = Path(__file__).parent / "fixtures" / "external-research-evidence-package.json"
        package = MODULE.load_package(fixture)
        self.assertEqual({source["status"] for source in package["sources"]}, {"unverified"})
        self.assertEqual({claim["review_status"] for claim in package["claims"]}, {"provisional"})
        self.assertTrue(all(source["locator"].startswith("https://") for source in package["sources"]))

    def test_block_claims_cannot_escape_section_scope(self):
        package = copy.deepcopy(VALID)
        package["sections"][0]["claim_refs"] = ["claim-1"]
        package["sections"][0]["blocks"][0]["claim_refs"] = ["claim-2"]
        with self.assertRaisesRegex(ValueError, "subset"):
            MODULE.validate_package(package)

    def test_irregular_tables_fail_closed(self):
        package = copy.deepcopy(VALID)
        package["sections"][0]["blocks"][2]["rows"].append(["extra", "cell", "rejected"])
        with self.assertRaisesRegex(ValueError, "rectangular"):
            MODULE.validate_package(package)

if __name__ == "__main__":
    unittest.main()
