"""Tests for optional editor hook installation."""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from knowledge_studio import cli as cli_module
from knowledge_studio.cli import app


runner = CliRunner()


def _init_instance(tmp_path):
    target = tmp_path / "kb"
    result = runner.invoke(
        app,
        ["init", str(target), "--no-git", "--no-set-default"],
    )
    assert result.exit_code == 0, result.output
    return target


def _load_codex_hooks(target):
    return json.loads((target / ".codex" / "hooks.json").read_text(encoding="utf-8"))


def _codex_commands(hooks, event):
    return [
        handler["command"]
        for group in hooks.get("hooks", {}).get(event, [])
        for handler in group.get("hooks", [])
        if handler.get("type") == "command"
    ]


def _bash_command():
    if os.name != "nt":
        return "bash"
    git = shutil.which("git.exe") or shutil.which("git")
    if git:
        git_root = Path(git).resolve().parent.parent
        candidate = git_root / "bin" / "bash.exe"
        if candidate.is_file():
            return str(candidate)
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        program_files = os.environ.get(variable)
        if program_files:
            candidate = Path(program_files) / "Git" / "bin" / "bash.exe"
            if candidate.is_file():
                return str(candidate)
    return "bash"


def _run_hook(script, payload, cwd, env_overrides=None):
    env = os.environ.copy()
    env["OKS_ROOT"] = str(cwd)
    if env_overrides:
        env.update(env_overrides)
    cli_root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = os.pathsep.join(
        [str(cli_root), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    command = (
        [_bash_command(), str(script)]
        if script.suffix == ".sh"
        else [sys.executable, str(script)]
    )
    return subprocess.run(
        command,
        input=json.dumps(payload),
        text=True,
        encoding="utf-8",
        capture_output=True,
        cwd=str(cwd),
        env=env,
        check=False,
    )


def test_hook_install_wires_codex_prompt_recall(tmp_path):
    target = _init_instance(tmp_path)

    result = runner.invoke(app, ["hook", "install", "--editor", "codex", "--path", str(target)])

    assert result.exit_code == 0, result.output
    hooks = _load_codex_hooks(target)
    commands = _codex_commands(hooks, "UserPromptSubmit")
    assert len(commands) == 1
    if os.name == "nt":
        assert sys.executable in commands[0]
        assert "user-prompt-recall.py" in commands[0]
    else:
        assert commands[0].endswith("/.codex/hooks/user-prompt-recall.sh")
    assert (target / ".codex" / "hooks" / "user-prompt-recall.sh").is_file()
    assert (target / ".codex" / "hooks" / "user-prompt-recall.py").is_file()

    # Existing Codex hooks remain intact.
    assert _codex_commands(hooks, "SessionStart")
    assert _codex_commands(hooks, "PreCompact")

    post_commands = _codex_commands(hooks, "PostToolUse")
    assert len(post_commands) == 1
    if os.name == "nt":
        assert sys.executable in post_commands[0]
        assert "post-tool-edit.py" in post_commands[0]
    else:
        assert post_commands[0].endswith("/.codex/hooks/post-tool-edit.sh")
    wrapper = target / ".codex" / "hooks" / "post-tool-edit.sh"
    shell_python = sys.executable.replace("\\", "/")
    assert f'${{OKS_PYTHON:-{shell_python}}}' in wrapper.read_text(encoding="utf-8")
    assert "/hooks" in result.output


def test_hook_install_wires_claude_prompt_recall(tmp_path):
    target = _init_instance(tmp_path)

    result = runner.invoke(
        app, ["hook", "install", "--editor", "claude", "--path", str(target)]
    )

    assert result.exit_code == 0, result.output
    settings = json.loads((target / ".claude" / "settings.json").read_text(encoding="utf-8"))
    prompt_handler = settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]
    post_handler = settings["hooks"]["PostToolUse"][0]["hooks"][0]
    if os.name == "nt":
        package_root = str(Path(cli_module.__file__).resolve().parents[1])
        runner_script = str((target / ".claude" / "hooks" / "_hook_runner.py").resolve())
        assert prompt_handler["command"] == sys.executable
        assert prompt_handler["args"] == [
            runner_script,
            str((target / ".claude" / "hooks" / "user-prompt-recall.py").resolve()),
            package_root,
        ]
        assert post_handler["command"] == sys.executable
        assert post_handler["args"] == [
            runner_script,
            str((target / ".claude" / "hooks" / "post-tool-edit.py").resolve()),
            package_root,
        ]
    else:
        assert prompt_handler["command"].endswith("/.claude/hooks/user-prompt-recall.sh")
        assert post_handler["command"].endswith("/.claude/hooks/post-tool-edit.sh")


def test_native_claude_runner_loads_mail_without_oks_environment(tmp_path):
    if os.name != "nt":
        pytest.skip("native Claude runner is a Windows hook path")

    from knowledge_studio import mail

    target = _init_instance(tmp_path)
    message = mail.write_message(
        target,
        body="native runner mail",
        sender="codex",
        recipients="@claude",
        title="Native runner",
    )
    hook_dir = target / ".claude" / "hooks"
    package_root = str(Path(cli_module.__file__).resolve().parents[1])
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"OKS_ROOT", "OKS_AGENT_ID", "OKS_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CLAUDECODE"}
    }
    env["OKS_HOOK_OUTPUT"] = "json"
    payload = json.dumps(
        {
            "prompt": "continue the native runner handoff",
            "session_id": "native-claude-session",
            "cwd": str(target),
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            str(hook_dir / "_hook_runner.py"),
            str(hook_dir / "user-prompt-recall.py"),
            package_root,
        ],
        input=payload.encode("utf-8"),
        capture_output=True,
        cwd=target,
        env=env,
    )

    stderr = (result.stderr or b"").decode("utf-8", errors="replace")
    assert result.returncode == 0, stderr
    raw_stdout = result.stdout or b""
    try:
        stdout = raw_stdout.decode("utf-8")
    except UnicodeDecodeError:
        stdout = raw_stdout.decode("gbk")
    output = json.loads(stdout)
    assert output["status"] == "injected"
    assert message["message_id"] in output["context"]
    assert mail.receipt_path(target, "native-claude-session", message["message_id"]).is_file()


def test_codex_python_command_quotes_paths_for_native_windows(tmp_path):
    hooks_dir = tmp_path / "instance with spaces" / ".codex" / "hooks"
    command = cli_module._codex_python_hook_command(
        hooks_dir,
        "user-prompt-recall.py",
        native_windows=True,
    )

    assert '"' in command
    assert '"' + str(hooks_dir.resolve()) + '\\user-prompt-recall.py"' in command
    assert command.endswith('user-prompt-recall.py" 2>NUL')


def test_hook_install_codex_is_idempotent_and_status_reports_wired(tmp_path):
    target = _init_instance(tmp_path)
    args = ["hook", "install", "--editor", "codex", "--path", str(target)]

    first = runner.invoke(app, args)
    second = runner.invoke(app, args)

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    hooks = _load_codex_hooks(target)
    commands = _codex_commands(hooks, "UserPromptSubmit")
    assert len(commands) == 1

    status = runner.invoke(app, ["hook", "status", "--path", str(target)])
    assert status.exit_code == 0, status.output
    assert "codex: wired" in status.output
    assert "codex PostToolUse: wired" in status.output
    assert "codex trust: review with `/hooks`" in status.output


def test_hook_install_refreshes_stale_prompt_hook_engine(tmp_path):
    target = _init_instance(tmp_path)
    script = target / ".codex" / "hooks" / "user-prompt-recall.py"
    script.write_text("# stale hook\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["hook", "install", "--editor", "codex", "--path", str(target)],
    )

    assert result.exit_code == 0, result.output
    assert "mail_domain.iter_messages" in script.read_text(encoding="utf-8")


def test_hook_install_migrates_codex_relative_lifecycle_paths(tmp_path):
    target = _init_instance(tmp_path)
    hooks_path = target / ".codex" / "hooks.json"
    hooks = _load_codex_hooks(target)
    legacy_commands = {
        "PreToolUse": "validate-wiki-write.sh",
        "PreCompact": "pre-compact.sh",
        "SessionStart": "session-start.sh",
    }
    for event, script_name in legacy_commands.items():
        hooks["hooks"][event][0]["hooks"][0]["command"] = f".codex/hooks/{script_name}"
    hooks_path.write_text(json.dumps(hooks, indent=2) + "\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["hook", "install", "--editor", "codex", "--path", str(target)],
    )

    assert result.exit_code == 0, result.output
    migrated = _load_codex_hooks(target)
    for event, script_name in legacy_commands.items():
        command = _codex_commands(migrated, event)[0]
        assert Path(command).resolve() == (target / ".codex" / "hooks" / script_name).resolve()


def test_codex_posttool_apply_patch_records_files_and_emits_json_context(tmp_path):
    target = _init_instance(tmp_path)
    script = target / ".codex" / "hooks" / "post-tool-edit.py"
    edited = target / "wiki" / "architecture.md"
    added = target / "docs" / "codex.md"
    target_records = target / "records" / "file-edits.jsonl"
    target_records.parent.mkdir(parents=True, exist_ok=True)
    target_records.write_text(
        json.dumps(
            {
                "agent_id": "other-agent",
                "file_path": str(edited),
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    patch_command = "\n".join(
        [
            "*** Begin Patch",
            "*** Update File: wiki/architecture.md",
            "@@",
            "+updated",
            "*** Add File: docs/codex.md",
            "+new",
            "*** End Patch",
        ]
    )
    result = _run_hook(
        script,
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "apply_patch",
            "tool_input": {"command": patch_command},
            "tool_response": {"status": "completed"},
            "session_id": "codex-session",
            "cwd": str(target),
            "agent_id": "codex-agent",
            "model": "gpt-5",
        },
        target,
        {"PYTHONIOENCODING": "cp1252"},
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "文件冲突" in output["hookSpecificOutput"]["additionalContext"]
    records = [
        json.loads(line)
        for line in target_records.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert {record["file_path"] for record in records[-2:]} == {
        str(edited),
        str(added),
    }


def test_codex_pretooluse_blocks_invalid_added_wiki_patch(tmp_path):
    target = _init_instance(tmp_path)
    script = target / ".codex" / "hooks" / "validate-wiki-write.sh"
    shell_python = sys.executable.replace("\\", "/")
    baked_python = f'${{OKS_PYTHON:-{shell_python}}}'
    assert baked_python in script.read_text(encoding="utf-8")
    invalid_patch = "\n".join(
        [
            "*** Begin Patch",
            "*** Add File: wiki/invalid.md",
            "+# Missing frontmatter",
            "*** End Patch",
        ]
    )
    blocked = _run_hook(
        script,
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "apply_patch",
            "tool_input": {"command": invalid_patch},
            "cwd": str(target),
        },
        target,
    )
    assert blocked.returncode == 2
    assert "frontmatter" in blocked.stderr

    valid_patch = "\n".join(
        [
            "*** Begin Patch",
            "*** Add File: wiki/valid.md",
            "+---",
            "+title: Valid",
            "+type: concept",
            "+area: computing",
            "+---",
            "+",
            "+# Valid",
            "*** End Patch",
        ]
    )
    allowed = _run_hook(
        script,
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "apply_patch",
            "tool_input": {"command": valid_patch},
            "cwd": str(target),
        },
        target,
    )
    assert allowed.returncode == 0, allowed.stderr

    legacy = _run_hook(
        script,
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": "wiki/legacy.md",
                "content": "# Missing frontmatter",
            },
            "cwd": str(target),
        },
        target,
    )
    assert legacy.returncode == 2
    assert "frontmatter" in legacy.stderr

    existing = target / "wiki" / "updated.md"
    existing.write_text(
        "---\ntitle: Existing\ntype: concept\narea: computing\n---\n\n# Existing\n",
        encoding="utf-8",
    )
    invalid_update = _run_hook(
        script,
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "apply_patch",
            "tool_input": {
                "command": "\n".join(
                    [
                        "*** Begin Patch",
                        "*** Update File: wiki/updated.md",
                        "@@",
                        "-title: Existing",
                        "+type: concept",
                        "*** End Patch",
                    ]
                )
            },
            "cwd": str(target),
        },
        target,
    )
    assert invalid_update.returncode == 2
    assert "title" in invalid_update.stderr


def test_codex_precompact_emits_json_system_message_and_saves_snapshot(tmp_path):
    target = _init_instance(tmp_path)
    script = target / ".codex" / "hooks" / "pre-compact.sh"
    shell_python = sys.executable.replace("\\", "/")
    baked_python = f'${{OKS_PYTHON:-{shell_python}}}'
    assert baked_python in script.read_text(encoding="utf-8")
    result = _run_hook(
        script,
        {
            "hook_event_name": "PreCompact",
            "session_id": "codex-session",
            "cwd": str(target),
            "model": "gpt-5",
        },
        target,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["systemMessage"].startswith("Snapshot saved:")
    assert list((target / ".oks" / "snapshots").glob("pre-compact-*.md"))

    legacy = _run_hook(
        script,
        {
            "hook_event_name": "PreCompact",
            "session_id": "claude-session",
            "cwd": str(target),
        },
        target,
    )
    assert legacy.returncode == 0, legacy.stderr
    assert legacy.stdout.startswith("Snapshot saved:")


def test_non_codex_posttool_keeps_plain_text_conflict_output(tmp_path):
    target = _init_instance(tmp_path)
    script = target / ".codex" / "hooks" / "post-tool-edit.py"
    edited = target / "wiki" / "legacy.md"
    records = target / "records" / "file-edits.jsonl"
    records.parent.mkdir(parents=True, exist_ok=True)
    records.write_text(
        json.dumps(
            {
                "agent_id": "other-agent",
                "file_path": str(edited),
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = _run_hook(
        script,
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": str(edited)},
            "session_id": "claude-session",
            "cwd": str(target),
            "agent_id": "claude-agent",
        },
        target,
        {"PYTHONIOENCODING": "cp1252"},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("[oks] 文件冲突:")
    assert not result.stdout.startswith("{")


def test_hook_recall_cli_reuses_policy_and_history_without_prompt_leakage(tmp_path):
    target = _init_instance(tmp_path)
    page = target / "wiki" / "computing" / "concepts" / "recall-bridge.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "---\n"
        "title: Recall bridge\n"
        "type: concept\n"
        "area: architecture\n"
        "status: active\n"
        "importance: 0.9\n"
        "confidence: 0.9\n"
        "created: 2026-08-20T00:00:00+00:00\n"
        "tags: recall, bridge, architecture\n"
        "pinned: false\n"
        "archived: false\n"
        "access_count: 0\n"
        "---\n\n"
        "The recall bridge keeps DSH as a thin adapter over OKS policy.\n",
        encoding="utf-8",
    )
    # The Hook contract is independent of an optional FTS index. Exercise the
    # deterministic native backend here; FTS lifecycle has its own test suite.
    recall_config = target / "settings" / "recall.yaml"
    recall_config.write_text(
        recall_config.read_text(encoding="utf-8").replace("search_backend: fts5", "search_backend: native"),
        encoding="utf-8",
    )
    args = [
        "hook", "recall", "recall bridge architecture", "--format", "json",
        "--path", str(target), "--session-id", "dsh-oks", "--cwd", "C:/dsh-host",
    ]

    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    payload = json.loads(first.output)
    assert payload["schema"] == "hook-recall-response/v1"
    assert payload["status"] == "injected"
    assert payload["trace"]["matches"] == ["recall-bridge"], payload
    assert "recall bridge architecture" not in json.dumps(payload)

    second = runner.invoke(app, args)
    assert second.exit_code == 0, second.output
    assert json.loads(second.output)["status"] == "skipped_cooldown"

    history = runner.invoke(
        app,
        [
            "hook", "history", "--format", "json", "--path", str(target),
            "--session-id", "dsh-oks", "--cwd", "C:/dsh-host",
        ],
    )
    assert history.exit_code == 0, history.output
    records = json.loads(history.output)
    assert records["schema"] == "hook-recall-history/v1"
    assert records["items"][0]["matches"] == ["recall-bridge"]
    assert "C:/dsh-host" not in history.output


def test_hook_recall_cli_rejects_malformed_success_envelope(tmp_path, monkeypatch):
    target = _init_instance(tmp_path)

    class Completed:
        returncode = 0
        stdout = json.dumps({
            "schema": "hook-recall-response/v1",
            "status": "invalid",
            "context": 123,
            "trace": None,
        })

    monkeypatch.setattr(cli_module.subprocess, "run", lambda *args, **kwargs: Completed())
    result = cli_module._run_hook_recall(target, "safe prompt", "session", "C:/host", "dsh-oks")

    assert result == {
        "schema": "hook-recall-response/v1",
        "status": "error",
        "context": "",
        "trace": {"candidate_count": 0, "matches": [], "top_relevance": None, "threshold": None},
        "reason": "hook_bridge_failed",
    }


def test_prompt_hook_degrades_loudly_without_mail_module(tmp_path):
    """A hook run without knowledge_studio warns on stderr and traces the gap."""
    target = _init_instance(tmp_path)
    result = runner.invoke(
        app,
        ["hook", "install", "--editor", "claude", "--path", str(target)],
    )
    assert result.exit_code == 0, result.output
    script = target / ".claude" / "hooks" / "user-prompt-recall.py"

    # A stub package whose import raises reproduces an environment where
    # knowledge_studio.mail is unavailable (e.g. wrong interpreter).
    stub = tmp_path / "stub" / "knowledge_studio"
    stub.mkdir(parents=True)
    (stub / "__init__.py").write_text(
        "raise ImportError('stub: mail unavailable')\n", encoding="utf-8"
    )
    env = os.environ.copy()
    env["OKS_ROOT"] = str(target)
    env["OKS_AGENT_ID"] = "claude"
    env["OKS_SESSION_ID"] = "degraded-session"
    env["PYTHONPATH"] = str(stub.parent)
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps({"session_id": "degraded-session", "prompt": "hello"}),
        text=True,
        encoding="utf-8",
        capture_output=True,
        cwd=str(target),
        env=env,
        check=False,
    )

    assert proc.returncode == 0
    assert "Mail injection disabled" in proc.stderr
    assert "<oks-mail-inbox" not in proc.stdout

    trace = target / "records" / "inject.jsonl"
    assert trace.is_file()
    records = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(record.get("event") == "mail_degraded" for record in records)
