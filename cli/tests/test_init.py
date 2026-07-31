"""Tests for `oks init` — instance scaffolding + shareable-asset materialization."""
from pathlib import Path

from typer.testing import CliRunner

from knowledge_studio.cli import app

runner = CliRunner()

# Contract: what `oks init` must produce. Buckets come from _INSTANCE_DIRS;
# .claude/templates/_meta/settings are the materialized shareable assets.
EXPECTED_BUCKETS = [
    "profiles/users", "profiles/projects", "profiles/recipes", "profiles/goals",
    "raw", "wiki", "drafts",
]
EXPECTED_TOP_LEVEL = {
    ".claude", "_meta", "settings", "templates",
    "profiles", "raw", "wiki", "drafts", ".gitignore",
}


def test_init_scaffolds_buckets_and_data_gitignore(tmp_path):
    target = tmp_path / "kb"
    result = runner.invoke(app, ["init", str(target), "--no-git", "--no-set-default"])
    assert result.exit_code == 0, result.output

    for d in EXPECTED_BUCKETS:
        assert (target / d).is_dir(), f"missing bucket {d}"

    gi = (target / ".gitignore").read_text(encoding="utf-8")
    # instance gitignore ignores only per-machine state, and TRACKS memory
    assert ".oks/" in gi
    assert "wiki/**/*.md" not in gi
    assert "drafts/*.md" not in gi


def test_init_structure_matches_contract_exactly(tmp_path):
    """Guard against silent drift between `oks init` and the documented layout."""
    target = tmp_path / "kb"
    result = runner.invoke(app, ["init", str(target), "--no-git", "--no-set-default"])
    assert result.exit_code == 0, result.output

    assert {entry.name for entry in target.iterdir()} == EXPECTED_TOP_LEVEL
    # A fresh instance carries no execution traces or proposals: those paths are
    # created on first use, so users who never trace never see the directories.
    assert not (target / "raw" / "executions").exists()
    assert not (target / "drafts" / "proposals").exists()


def test_trace_and_proposal_paths_are_created_on_demand(tmp_path, monkeypatch):
    """`oks trace` must work on a freshly initialized instance."""
    target = tmp_path / "kb"
    assert runner.invoke(app, ["init", str(target), "--no-git", "--no-set-default"]).exit_code == 0
    monkeypatch.setenv("OKS_ROOT", str(target))

    from knowledge_studio.proposals import create_proposal
    from knowledge_studio.trace import start_trace

    start_trace("goal-init", "run-init")
    run_dir = target / "raw" / "executions" / "run-init"
    assert (run_dir / "events.jsonl").is_file()
    assert (run_dir / "run.json").is_file()

    proposal = create_proposal("run-init", "wiki", "Init lesson", "Scaffold works.")
    assert proposal.parent == target / "drafts" / "proposals" / "wiki"


def test_init_materializes_shareable_assets(tmp_path):
    target = tmp_path / "kb"
    result = runner.invoke(app, ["init", str(target), "--no-git", "--no-set-default"])
    assert result.exit_code == 0, result.output

    # skills + templates arrive so the Claude Code experience works out of the box
    assert (target / ".claude" / "skills" / "ingest").is_dir()
    assert (target / ".claude" / "settings.json").is_file()
    assert (target / "templates").is_dir()
    for schema in ("recall-case.schema.json", "trace-event.schema.json", "run-manifest.schema.json"):
        assert (target / "_meta" / schema).is_file()


def test_init_upgrade_refreshes_assets_but_keeps_user_files(tmp_path):
    target = tmp_path / "kb"
    runner.invoke(app, ["init", str(target), "--no-git", "--no-set-default"])

    marker = target / ".claude" / "MARKER.txt"
    marker.write_text("local edit", encoding="utf-8")

    bundled = target / ".claude" / "settings.json"
    original = bundled.read_text(encoding="utf-8")
    bundled.write_text("{}", encoding="utf-8")

    # re-init without --upgrade keeps existing assets untouched
    runner.invoke(app, ["init", str(target), "--no-git", "--no-set-default"])
    assert marker.exists()
    assert bundled.read_text(encoding="utf-8") == "{}"

    # --upgrade merge-copies bundled assets: bundled files refreshed,
    # user-owned files (marker) survive — no more whole-tree deletion
    runner.invoke(app, ["init", str(target), "--no-git", "--no-set-default", "--upgrade"])
    assert marker.exists()
    assert bundled.read_text(encoding="utf-8") == original


def test_init_requires_path_argument():
    result = runner.invoke(app, ["init"])
    assert result.exit_code != 0


def test_init_aborts_on_nonempty_non_kb_dir(tmp_path):
    target = tmp_path / "documents"
    target.mkdir()
    (target / "important.txt").write_text("do not touch", encoding="utf-8")

    result = runner.invoke(app, ["init", str(target), "--no-git", "--no-set-default"])
    assert result.exit_code == 1
    assert not (target / "wiki").exists()

    # --force overrides the guard
    result = runner.invoke(
        app, ["init", str(target), "--no-git", "--no-set-default", "--force"]
    )
    assert result.exit_code == 0, result.output
    assert (target / "wiki").is_dir()
    assert (target / "important.txt").exists()


def test_init_rerun_on_existing_kb_is_idempotent(tmp_path):
    target = tmp_path / "kb"
    result = runner.invoke(app, ["init", str(target), "--no-git", "--no-set-default"])
    assert result.exit_code == 0, result.output

    # target now contains wiki/ → treated as an existing KB, no --force needed
    result = runner.invoke(app, ["init", str(target), "--no-git", "--no-set-default"])
    assert result.exit_code == 0, result.output
