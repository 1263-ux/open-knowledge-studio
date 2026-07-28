from typer.testing import CliRunner

from knowledge_studio import cli


runner = CliRunner()


def test_ingest_missing_connector_shows_explicit_action(monkeypatch):
    monkeypatch.setattr(cli, "_connector_command", lambda: None)

    result = runner.invoke(cli.app, ["ingest", "https://example.com/video"])

    assert result.exit_code == 2
    assert "Connector" in result.output  # appears in both zh/en
    assert result.exit_code == 2


def test_ingest_recommends_capability_install(monkeypatch):
    """Pre-flight check suggests capability install when extractor is missing."""
    monkeypatch.setattr(cli, "_connector_command", lambda: "built-in")
    monkeypatch.setattr(cli, "_capability_already_installed", lambda _name: False)

    result = runner.invoke(cli.app, ["ingest", "paper.pdf"])

    assert result.exit_code == 2
    assert "capability install" in result.output  # appears in both zh/en


def test_connector_command_reports_builtin_when_module_available(monkeypatch):
    """After repo merge, _connector_command returns 'built-in' when the module is importable."""
    monkeypatch.setattr(cli, "_connector_available", True)

    assert cli._connector_command() == "built-in"


def test_ingest_forwards_mode_timeout_and_progress(monkeypatch):
    received = {}

    def fake_run_ingest(parsed):
        received["mode"] = parsed.mode
        received["timeout"] = getattr(parsed, "timeout_seconds", None)
        received["progress"] = getattr(parsed, "progress", False)
        received["source"] = parsed.source
        return 0

    monkeypatch.setattr(cli, "_connector_command", lambda: "built-in")
    monkeypatch.setattr(cli, "_capability_already_installed", lambda _name: True)
    monkeypatch.setattr(cli, "_connector_run_ingest", fake_run_ingest)

    result = runner.invoke(
        cli.app,
        ["ingest", "https://example.com/video", "--mode", "forensic", "--timeout-seconds", "30"],
    )

    assert result.exit_code == 0, result.output
    assert received["mode"] == "forensic"
    assert received["timeout"] == 30.0
    assert received["progress"] is True


def test_ingest_forwards_formula_secondary_for_pdf(monkeypatch):
    received = {}

    def fake_run_ingest(parsed):
        received["formula_secondary"] = parsed.formula_secondary
        received["formula_max_regions"] = parsed.formula_max_regions
        return 0

    monkeypatch.setattr(cli, "_connector_command", lambda: "built-in")
    monkeypatch.setattr(cli, "_capability_already_installed", lambda _name: True)
    monkeypatch.setattr(cli, "_connector_run_ingest", fake_run_ingest)

    result = runner.invoke(
        cli.app,
        ["ingest", "paper.pdf", "--formula-secondary", "--formula-max-regions", "7"],
    )

    assert result.exit_code == 0, result.output
    assert received == {"formula_secondary": True, "formula_max_regions": 7}


def test_capability_install_is_explicit_by_default():
    result = runner.invoke(cli.app, ["capability", "install", "watch"])

    assert result.exit_code == 0, result.output
    assert "pip" in result.output  # pip install command shown (may wrap in panel)
    assert "--yes" in result.output


def test_feishu_missing_worker_is_actionable(monkeypatch):
    monkeypatch.setattr(cli, "_feishu_worker_path", lambda: None)

    result = runner.invoke(cli.app, ["feishu", "run-once"])

    assert result.exit_code == 2
    assert "OKS_FEISHU_WORKER" in result.output


def test_feishu_form_is_human_visible():
    result = runner.invoke(cli.app, ["feishu", "form", "--url", "https://example.feishu.cn/form"])

    assert result.exit_code == 0
    assert "https://example.feishu.cn/form" in result.output


def test_feishu_submit_forwards_optional_context(monkeypatch):
    received = []
    monkeypatch.setattr(cli, "_run_feishu_worker", lambda command, extra: received.extend([command, *extra]))

    result = runner.invoke(
        cli.app, ["feishu", "submit", "https://example.com", "--thought", "watch", "--rating", "A"]
    )

    assert result.exit_code == 0, result.output
    assert received == ["enqueue", "https://example.com", "--thought", "watch", "--rating", "A"]


def test_feishu_capability_never_bundles_tenant_configuration():
    result = runner.invoke(cli.app, ["capability", "install", "feishu"])

    assert result.exit_code == 0, result.output
    assert "lark-cli" in result.output  # appears in both zh/en
