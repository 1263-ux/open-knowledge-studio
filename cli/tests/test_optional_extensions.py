from typer.testing import CliRunner

from knowledge_studio import cli


runner = CliRunner()


def test_ingest_missing_connector_shows_explicit_pipx_action(monkeypatch):
    monkeypatch.setattr(cli, "_connector_command", lambda: None)

    result = runner.invoke(cli.app, ["ingest", "https://example.com/video"])

    assert result.exit_code == 2
    assert "pipx inject open-knowledge-studio oks-connector" in result.output
    assert "Action required" in result.output


def test_ingest_recommends_the_pdf_component(monkeypatch):
    monkeypatch.setattr(cli, "_connector_command", lambda: None)

    result = runner.invoke(cli.app, ["ingest", "paper.pdf"])

    assert result.exit_code == 2
    assert "Recommended for this source: pdf" in result.output
    assert "oks-connector[pdf]" in result.output


def test_ingest_forwards_mode_timeout_and_progress(monkeypatch):
    command = []

    class Result:
        returncode = 0

    monkeypatch.setattr(cli, "_connector_command", lambda: "oks-connector")
    monkeypatch.setattr(cli.subprocess, "run", lambda argv: command.extend(argv) or Result())

    result = runner.invoke(
        cli.app,
        ["ingest", "https://example.com/video", "--mode", "forensic", "--timeout-seconds", "30"],
    )

    assert result.exit_code == 0, result.output
    assert command == [
        "oks-connector", "ingest", "https://example.com/video", "--mode", "forensic",
        "--timeout-seconds", "30.0", "--progress",
    ]


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


def test_capability_install_is_explicit_by_default():
    result = runner.invoke(cli.app, ["capability", "install", "watch"])

    assert result.exit_code == 0, result.output
    assert "pipx inject open-knowledge-studio oks-connector[watch]" in result.output
    assert "--yes" in result.output


def test_feishu_capability_never_bundles_tenant_configuration():
    result = runner.invoke(cli.app, ["capability", "install", "feishu"])

    assert result.exit_code == 0, result.output
    assert "No tenant credentials" in result.output
