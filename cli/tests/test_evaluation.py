"""Tests for deterministic, read-only recall evaluation."""
import json

import yaml

from knowledge_studio.evaluation import compare_runs, load_dataset, run_evaluation
from knowledge_studio.store import _atomic_write


def _page(path, title, body, *, page_type="concept", tags="recall"):
    meta = {
        "title": title, "type": page_type, "area": "computing",
        "status": "active", "importance": 0.8, "confidence": 0.8,
        "created": "2026-07-27T00:00:00Z", "pinned": False,
        "archived": False, "tags": tags,
    }
    fm = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
    _atomic_write(path, f"---\n{fm}---\n\n{body}")


def _dataset(path):
    data = {
        "schema_version": "recall-case/v1", "dataset_id": "unit",
        "version": "1", "cases": [{
            "case_id": "c1", "query": "alpha recall", "goal": "none",
            "relevant": ["alpha"], "forbidden": ["stale"],
        }],
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_evaluation_metrics_manifest_and_read_only(tmp_path, monkeypatch):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    wiki = tmp_path / "wiki" / "computing" / "concepts"
    wiki.mkdir(parents=True)
    _page(wiki / "alpha.md", "Alpha Recall", "alpha recall is the expected page")
    _page(wiki / "stale.md", "Unrelated", "not a matching document", tags="other")
    dataset = _dataset(tmp_path / "dataset.yaml")
    before = (wiki / "alpha.md").read_bytes()

    result = run_evaluation(dataset, tmp_path / "runs" / "one.json")

    assert result["metrics"]["recall_at_1"] == 1.0
    assert result["metrics"]["mrr"] == 1.0
    assert result["metrics"]["stale_leakage"] == 0.0
    assert result["manifest"]["dataset_sha256"]
    assert result["manifest"]["kb_snapshot_before"] == result["manifest"]["kb_snapshot_after"]
    assert (wiki / "alpha.md").read_bytes() == before
    assert not (tmp_path / ".oks").exists()


def test_dataset_validation_and_run_comparison(tmp_path, monkeypatch):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    wiki = tmp_path / "wiki" / "computing" / "concepts"
    wiki.mkdir(parents=True)
    _page(wiki / "alpha.md", "Alpha Recall", "alpha recall")
    dataset = _dataset(tmp_path / "dataset.yaml")
    assert load_dataset(dataset)["dataset_id"] == "unit"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    run_evaluation(dataset, first)
    run_evaluation(dataset, second)
    comparison = compare_runs(first, second, tmp_path / "comparison.json")
    assert comparison["deltas"]["recall_at_5"] == 0.0
    assert comparison["goal_lift"]["recall_at_5"] == 0.0
    assert json.loads((tmp_path / "comparison.json").read_text())["schema_version"] == "recall-eval-comparison/v1"


def test_compare_rejects_different_dataset_snapshots(tmp_path):
    left = {"schema_version": "recall-eval-run/v1", "manifest": {"dataset_sha256": "a"}, "metrics": {}}
    right = {"schema_version": "recall-eval-run/v1", "manifest": {"dataset_sha256": "b"}, "metrics": {}}
    (tmp_path / "left.json").write_text(json.dumps(left), encoding="utf-8")
    (tmp_path / "right.json").write_text(json.dumps(right), encoding="utf-8")
    try:
        compare_runs(tmp_path / "left.json", tmp_path / "right.json")
    except ValueError as exc:
        assert "different dataset" in str(exc)
    else:
        raise AssertionError("comparison should reject different datasets")
