"""Tests for generic Agent skill installation and binding."""
import json
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from knowledge_studio import cli
from knowledge_studio.mail_setup import install_skill


def _kb(tmp_path):
    (tmp_path / "mail").mkdir(parents=True)
    (tmp_path / "wiki").mkdir(parents=True)
    return tmp_path


def test_setup_installs_a_bound_skill_idempotently(tmp_path):
    root = _kb(tmp_path / "kb")
    target = tmp_path / "skills"
    installed = install_skill(root, "@reviewer", target)
    assert installed == (target / "oks-mail").resolve()
    binding = json.loads((installed / "binding.json").read_text(encoding="utf-8"))
    assert binding == {"knowledge_base": str(root.resolve()), "agent_id": "reviewer"}
    before = {p.relative_to(installed): p.read_bytes() for p in installed.rglob("*") if p.is_file()}
    assert install_skill(root, "reviewer", target) == installed
    assert before == {p.relative_to(installed): p.read_bytes() for p in installed.rglob("*") if p.is_file()}


def test_setup_refuses_a_different_existing_binding(tmp_path):
    root = _kb(tmp_path / "kb")
    target = tmp_path / "skills"
    install_skill(root, "reviewer", target)
    with pytest.raises(ValueError, match="Existing skill differs"):
        install_skill(root, "other-agent", target)


@pytest.mark.parametrize("agent", ["human", "all", "unknown", "../escape", "a/b", ""])
def test_setup_rejects_reserved_or_unsafe_agent_ids(tmp_path, agent):
    with pytest.raises(ValueError):
        install_skill(_kb(tmp_path / "kb"), agent, tmp_path / "skills")


def test_cli_setup_uses_explicit_kb_and_skills_directory(tmp_path):
    root = _kb(tmp_path / "kb")
    target = tmp_path / "host-skills"
    result = CliRunner().invoke(
        cli.app,
        ["mail", "setup", "--agent", "codex", "--path", str(root), "--skills-dir", str(target)],
    )
    assert result.exit_code == 0, result.stdout
    assert (target / "oks-mail" / "scripts" / "mail.py").is_file()


def test_installed_helper_reads_the_bound_mailbox(tmp_path):
    root = _kb(tmp_path / "kb")
    target = tmp_path / "host-skills"
    install_skill(root, "reviewer", target)
    helper = target / "oks-mail" / "scripts" / "mail.py"
    env = {**__import__("os").environ, "PYTHONPATH": str(__import__("pathlib").Path(__file__).parents[1])}
    result = subprocess.run([sys.executable, str(helper), "snapshot"], env=env, capture_output=True, text=True, encoding="utf-8", check=True)
    payload = json.loads(result.stdout)
    assert payload["agent"] == "@reviewer"
    assert payload["threads"] == []
