from pathlib import Path
import unittest


SKILL = Path(__file__).parents[1] / "SKILL.md"


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


if __name__ == "__main__":
    unittest.main()
