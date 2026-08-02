"""Build hook: vendor the instance-template assets and the connector package.

`assets/` at the repo root is the single source for everything an instance
gets: skills, hooks, rules, templates, _meta, settings, per-agent config.
Maintainer-only tooling lives in the repo's own `.claude/`, outside `assets/` —
physical separation instead of ignore rules.

Building from a git checkout copies `assets/` into `knowledge_studio/_assets/`
and `scripts/` into `oks_connector/`, so source installs, sdists and PyPI
wheels are identical. A `package-dir` pointing at `../scripts` cannot reach
into an sdist, which is why the connector is vendored here. When building from
an sdist the repo root is absent and both trees already exist — skip silently.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

# Test modules would collide with the repo-root copies during collection;
# caches are build noise.
_CONNECTOR_IGNORE = shutil.ignore_patterns("test_*.py", "tests", "__pycache__", "*.pyc")
_ASSET_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")

# `oks feishu` resolves the worker from _assets/scripts/ (see cli.py), so it is
# vendored alongside the template tree.
_SCRIPT_ASSETS = ("feishu_base_worker.py", "feishu_setup.py")


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
    """Copy ../assets verbatim into knowledge_studio/_assets/."""
    repo_root = _repo_root()
    source = repo_root / "assets"
    if not source.is_dir():
        return
    dest_root = Path(__file__).resolve().parent / "knowledge_studio" / "_assets"
    if dest_root.exists():
        shutil.rmtree(dest_root)
    shutil.copytree(source, dest_root, ignore=_ASSET_IGNORE)

    scripts_dest = dest_root / "scripts"
    scripts_dest.mkdir(parents=True, exist_ok=True)
    for name in _SCRIPT_ASSETS:
        script = repo_root / "scripts" / name
        if script.is_file():
            shutil.copy2(script, scripts_dest / name)


def _purge_stale_build_copies(*relative: str) -> None:
    """Drop build/lib mirrors of vendored trees.

    build_py copies into build/lib incrementally and never deletes, so a tree
    vendored before a layout change keeps shipping from there — observed as
    removed maintainer skills reappearing in a fresh wheel.
    """
    build_lib = Path(__file__).resolve().parent / "build" / "lib"
    for name in relative:
        stale = build_lib / name
        if stale.exists():
            shutil.rmtree(stale, ignore_errors=True)


def _sync_from_checkout() -> None:
    if (_repo_root() / "assets").is_dir():
        _purge_stale_build_copies("knowledge_studio/_assets", "oks_connector")
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
