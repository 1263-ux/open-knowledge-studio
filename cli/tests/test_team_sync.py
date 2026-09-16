import subprocess

from knowledge_studio.team_sync import status, sync


def git(cwd, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=check, capture_output=True,
        text=True, encoding="utf-8",
    )


def test_team_status_without_git_is_actionable(tmp_path):
    result = status(tmp_path)
    assert result["state"] == "not_git"
    assert "Git" in result["message"]


def test_team_sync_commits_shared_folders_and_pushes(tmp_path):
    root = tmp_path / "team"
    root.mkdir()
    for name in ("mail", "raw", "drafts", "wiki", "profiles"):
        (root / name).mkdir()
    (root / "mail" / "message.md").write_text("# Mail\n", encoding="utf-8")
    (root / "mail" / ".recipient-state.lock").write_text("runtime lock\n", encoding="utf-8")
    (root / "settings").mkdir()
    (root / "settings" / "local.toml").write_text("local = true\n", encoding="utf-8")
    remote = tmp_path / "team.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "team@example.test")
    git(root, "config", "user.name", "OKS Team")
    git(root, "remote", "add", "origin", str(remote))
    git(root, "add", "settings/local.toml")

    result = sync(root, push=True)

    assert result["actions"] == ["commit", "push"]
    assert result["state"] == "clean"
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "--branch", "main", str(remote), str(clone))
    assert (clone / "mail" / "message.md").is_file()
    assert not (clone / "mail" / ".recipient-state.lock").exists()
    assert not (clone / "settings" / "local.toml").exists()
    assert "settings/local.toml" in git(root, "diff", "--cached", "--name-only").stdout.splitlines()
    assert not (root / ".agents" / "skills" / "oks-mail" / "binding.json").exists()


def test_team_sync_treats_notifications_as_local_runtime_state(tmp_path):
    root = tmp_path / "team"
    (root / "mail" / "notifications" / "codex").mkdir(parents=True)
    (root / "mail" / "message.md").write_text("# Mail\n", encoding="utf-8")
    (root / "mail" / "notifications" / "codex" / "msg_1.json").write_text(
        '{"status": "pending"}\n', encoding="utf-8"
    )
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "team@example.test")
    git(root, "config", "user.name", "OKS Team")

    result = status(root)
    paths = [change["path"] for change in result["changes"]]
    assert "mail/message.md" in paths
    assert "mail/notifications/codex/msg_1.json" not in paths
    assert result["ignored_changes"] >= 1

    synced = sync(root)
    assert synced["actions"] == ["commit"]
    committed = git(root, "show", "--name-only", "--format=", "HEAD").stdout.splitlines()
    assert committed == ["mail/message.md"]
    assert git(root, "diff", "--cached", "--name-only").stdout.strip() == ""
