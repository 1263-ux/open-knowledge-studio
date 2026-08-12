#!/usr/bin/env python3
"""Bundle the instance-template assets into the package as data, before build.

`<repo>/assets` is the single source for everything an instance receives —
skills, hooks, rules, templates, _meta, settings, profiles, per-agent config.
It is copied verbatim to `cli/knowledge_studio/_assets`.

Maintainer-only tooling lives in the repo's own `.claude/`, outside `assets/`,
so it cannot reach a user's knowledge base — physical separation instead of
ignore rules.

Keep this in sync with `cli/setup.py::_vendor_assets`: the publish workflow runs
this script explicitly, while a pip build goes through setup.py. Both must
produce the same tree.

Run before `python -m build` (the publish workflow does this). The bundled
`_assets/` dir is gitignored — it is a build artifact, not source.
"""
from __future__ import annotations

import shutil
from pathlib import Path

_ASSET_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")

def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]  # cli/scripts/x.py -> repo root
    source = repo_root / "assets"
    dest_root = repo_root / "cli" / "knowledge_studio" / "_assets"

    if not source.is_dir():
        raise SystemExit(f"assets/ not found at {source} — run this from a source checkout")

    if dest_root.exists():
        shutil.rmtree(dest_root)
    shutil.copytree(source, dest_root, ignore=_ASSET_IGNORE)
    copied = sorted(entry.name for entry in dest_root.iterdir())

    print(f"Bundled assets into {dest_root}: {', '.join(copied)}")


if __name__ == "__main__":
    main()
