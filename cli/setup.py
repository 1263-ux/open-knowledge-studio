"""Build hook: vendor the shareable asset layer and the connector package.

The repo root is the single source of truth for `.claude/`, `templates/`,
`_meta/`, `settings/` and `scripts/`. Building from a git checkout copies them
into `knowledge_studio/_assets/` and `oks_connector/` before the build runs, so
source installs, sdists and PyPI wheels are identical. A `package-dir` pointing
at `../scripts` cannot reach into an sdist, which is why the connector is
vendored here instead. When building from an sdist the repo root is absent and
both trees are already present — skip silently.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

_MAP = [
    (".claude", "claude"),
    (".codex", "codex"),
    (".agents", "agents"),
    ("templates", "templates"),
    ("_meta", "_meta"),
    ("settings", "settings"),
]

# Test modules would collide with the repo-root copies during collection;
# caches are build noise.
_CONNECTOR_IGNORE = shutil.ignore_patterns("test_*.py", "tests", "__pycache__", "*.pyc")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _vendor_connector() -> None:
    """Copy ../scripts into cli/oks_connector/ so it reaches sdists and wheels."""
    source = _repo_root() / "scripts"
    if not source.is_dir():
        return
    dest = Path(__file__).resolve().parent / "oks_connector"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest, ignore=_CONNECTOR_IGNORE)


def _vendor_assets() -> None:
    repo_root = _repo_root()
    dest_root = Path(__file__).resolve().parent / "knowledge_studio" / "_assets"
    if dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True)
    for src_name, dest_name in _MAP:
        src = repo_root / src_name
        if src.is_dir():
            shutil.copytree(src, dest_root / dest_name)
    worker = repo_root / "scripts" / "feishu_base_worker.py"
    if worker.is_file():
        worker_dest = dest_root / "scripts"
        worker_dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(worker, worker_dest / worker.name)


def _sync_from_checkout() -> None:
    repo_root = _repo_root()
    if (repo_root / ".claude").is_dir() and (repo_root / "templates").is_dir():
        _vendor_assets()
        _vendor_connector()


class build_py_with_assets(build_py):
    def run(self):
        _sync_from_checkout()
        super().run()


class sdist_with_assets(sdist):
    def run(self):
        _sync_from_checkout()
        super().run()


setup(cmdclass={"build_py": build_py_with_assets, "sdist": sdist_with_assets})
