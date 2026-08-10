import json
from pathlib import Path

from knowledge_studio.ingest_prepare import prepare_ingest


def _source_envelope(result: dict) -> dict:
    path = Path(result["manifest_dir"]) / "source-envelope.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_remote_source_requires_explicit_processing_decision(tmp_path):
    result = prepare_ingest("https://example.com/private?token=sample", kb_root=tmp_path)

    assert _source_envelope(result)["policy"]["remote_processing"] == "ask"


def test_local_source_denies_remote_processing_by_default(tmp_path):
    source = tmp_path / "notes.txt"
    source.write_text("local knowledge", encoding="utf-8")

    result = prepare_ingest(str(source), kb_root=tmp_path)

    assert _source_envelope(result)["policy"]["remote_processing"] == "deny"
