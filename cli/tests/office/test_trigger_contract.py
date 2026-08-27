from pathlib import Path
import unittest


ROOT = Path(__file__).parents[3]
OFFICE = ROOT / "assets" / "skills" / "office"
SKILL = OFFICE / "SKILL.md"
EVIDENCE_CONTRACT = OFFICE / "references" / "evidence-contract.md"
ROUTING = OFFICE / "references" / "adapter-routing.md"


class OfficeTriggerContractTests(unittest.TestCase):
    def test_office_requires_an_explicit_office_file_request(self):
        text = SKILL.read_text(encoding="utf-8")
        for format_name in ("Word", "DOCX", "Excel", "XLSX", "PowerPoint", "PPTX", "PDF"):
            self.assertIn(format_name, text)
        self.assertIn('Do **not** trigger it merely because a user says "write a', text)

    def test_research_precedes_oks_recall_in_every_office_run(self):
        text = SKILL.read_text(encoding="utf-8")
        research = text.index("2. Research the topic as a fixed step.")
        recall = text.index("3. Recall relevant OKS knowledge")
        self.assertLess(research, recall)

        contract = EVIDENCE_CONTRACT.read_text(encoding="utf-8")
        self.assertLess(
            contract.index("1. Research the topic as a fixed baseline."),
            contract.index("3. Recall relevant OKS knowledge"),
        )

    def test_xlsx_is_routed_to_the_host_skill_not_a_nonexistent_local_builder(self):
        text = ROUTING.read_text(encoding="utf-8")
        self.assertIn("Host `spreadsheets` skill", text)
        self.assertNotIn("openpyxl", text)


if __name__ == "__main__":
    unittest.main()
