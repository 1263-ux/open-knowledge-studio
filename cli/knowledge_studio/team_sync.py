"""Small-team Git transport for an OKS knowledge-base instance.

The sync surface is intentionally boring: shared OKS folders are staged and
committed, then an optional pull --rebase and push are performed.  Host-local
bindings and runtime locks never enter the staged set.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


SYNC_PATHS = ("mail", "raw", "drafts", "wiki", "profiles")
EXCLUDE_PATHS = (
    ":(exclude)**/*.lock",
    ":(exclude)**/*.tmp",
    ":(exclude)mail/notifications",
)


class TeamSyncError(RuntimeError):
    """A recoverable Git workflow error suitable for CLI/UI display."""


def _shared_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in SYNC_PATHS)


def _runtime_path(path: str) -> bool:
    # Locks and notifications are machine-local runtime state: lock files are
    # ephemeral, and notification intents are per-machine presentation state
    # that no other clone can act on.
    return path.endswith((".lock", ".tmp")) or path.startswith("mail/notifications/")


def _run(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise TeamSyncError(f"无法运行 Git：{exc}") from exc
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "Git 命令失败").strip()
        raise TeamSyncError(detail)
    return result


def _repo_root(root: Path) -> Path:
    root = root.expanduser().resolve()
    result = _run(root, "rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        raise TeamSyncError("这个知识库还不是 Git 仓库；先用 `oks team init <路径>` 创建。")
    actual = Path((result.stdout or "").strip()).resolve()
    if actual != root:
        raise TeamSyncError(f"请从知识库根目录同步：{actual}")
    return root


def _remote(root: Path) -> str:
    result = _run(root, "remote", "get-url", "origin", check=False)
    return (result.stdout or "").strip() if result.returncode == 0 else ""


def status(root: Path) -> dict:
    """Return a read-only, JSON-friendly summary of the shared Git state."""
    root = root.expanduser().resolve()
    probe = _run(root, "rev-parse", "--show-toplevel", check=False)
    if probe.returncode != 0:
        return {
            "schema": "oks.team-sync.v1",
            "state": "not_git",
            "branch": "",
            "remote": "",
            "changes": [],
            "ignored_changes": 0,
            "message": "当前知识库还没有 Git；先初始化团队空间。",
        }
    actual = Path((probe.stdout or "").strip()).resolve()
    if actual != root:
        return {
            "schema": "oks.team-sync.v1",
            "state": "wrong_root",
            "branch": "",
            "remote": "",
            "changes": [],
            "ignored_changes": 0,
            "message": f"请从知识库根目录操作：{actual}",
        }
    branch = (_run(root, "branch", "--show-current", check=False).stdout or "").strip()
    remote = _remote(root)
    porcelain = (_run(root, "status", "--porcelain=v1", "--untracked-files=all").stdout or "").splitlines()
    changes = []
    ignored = 0
    for line in porcelain:
        path = line[3:].strip() if len(line) >= 4 else line.strip()
        if _runtime_path(path):
            ignored += 1
            continue
        if _shared_path(path):
            changes.append({"path": path, "index": line[0:1], "worktree": line[1:2]})
        else:
            ignored += 1
    state = "dirty" if changes else ("no_remote" if not remote else "clean")
    return {
        "schema": "oks.team-sync.v1",
        "state": state,
        "branch": branch or "(detached)",
        "remote": remote,
        "changes": changes,
        "ignored_changes": ignored,
        "message": "有待同步的团队文件。" if changes else ("已配置远端，可同步。" if remote else "已初始化本地 Git，但还没有 origin 远端。"),
    }


def sync(root: Path, *, push: bool = False, message: str = "同步 OKS 团队资料") -> dict:
    """Commit shared folders, rebase from origin, and optionally push."""
    root = _repo_root(root)
    existing = [path for path in SYNC_PATHS if (root / path).exists()]
    if existing:
        # Mail creates short-lived lock/temp files while Agents and the UI are
        # reading it. They are machine-local runtime noise, not team facts.
        _run(root, "add", "--", *existing, *EXCLUDE_PATHS)
    staged = [
        path for path in (_run(root, "diff", "--cached", "--name-only").stdout or "").splitlines()
        if _shared_path(path) and not _runtime_path(path)
    ]
    actions = []
    if staged:
        # Use an explicit path list so a user's pre-staged settings/code files
        # cannot be swept into the team commit.
        _run(root, "commit", "-m", message.strip() or "同步 OKS 团队资料", "--", *staged)
        actions.append("commit")
    remote = _remote(root)
    if remote:
        branch = (_run(root, "branch", "--show-current", check=False).stdout or "").strip()
        remote_has_branch = bool(branch and (_run(root, "ls-remote", "--heads", "origin", branch, check=False).stdout or "").strip())
        if remote_has_branch:
            _run(root, "pull", "--rebase", "--autostash")
            actions.append("pull")
        if push:
            upstream = _run(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False)
            if branch and upstream.returncode != 0:
                _run(root, "push", "--set-upstream", "origin", branch)
            else:
                _run(root, "push")
            actions.append("push")
    elif push:
        raise TeamSyncError("还没有 origin 远端；先在团队空间配置一次 Git remote。")
    result = status(root)
    result["actions"] = actions
    result["message"] = "、".join(actions) if actions else "没有新的团队文件需要同步。"
    return result
