#!/usr/bin/env python3
"""Schema single-source sync (CONSTITUTION P8: one contract, one implementation).

`schemas/` at the repo root is the authoritative home for wire-format JSON
schemas. Two copies exist downstream and must agree with it:

- `assets/_meta/schemas/`   — materialized into instances by `oks init`
- `cli/knowledge_studio/schemas/` — runtime validation mirror inside the package

This script copies root -> mirrors. `--check` verifies agreement without
writing and exits 1 on drift; CI runs `--check` so the three trees cannot
silently diverge again (capture-envelope once lost `remote_api` in the
assets copy and nothing caught it).

Usage:
    python scripts/sync_schemas.py           # sync mirrors from root
    python scripts/sync_schemas.py --check   # verify only, exit 1 on drift
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "schemas"
MIRRORS = [
    REPO / "assets" / "_meta" / "schemas",
    REPO / "cli" / "knowledge_studio" / "schemas",
]


def digests(path: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(path.glob("*.json"))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify only; exit 1 on drift")
    args = parser.parse_args()

    if not SOURCE.is_dir():
        print(f"source directory missing: {SOURCE}")
        return 1

    source_files = digests(SOURCE)
    problems: list[str] = []

    for mirror in MIRRORS:
        if not mirror.is_dir():
            problems.append(f"{mirror.relative_to(REPO)}: directory missing")
            continue
        mirror_files = digests(mirror)
        for name, data in source_files.items():
            current = mirror_files.get(name)
            if current == data:
                continue
            if current is None:
                problems.append(f"{mirror.relative_to(REPO)}/{name}: missing")
            else:
                problems.append(f"{mirror.relative_to(REPO)}/{name}: differs from schemas/")
        for name in mirror_files:
            if name not in source_files:
                problems.append(
                    f"{mirror.relative_to(REPO)}/{name}: not in schemas/ (stale mirror?)"
                )

    if args.check:
        if problems:
            print("SCHEMA DRIFT — run `python scripts/sync_schemas.py` and commit:")
            for problem in problems:
                print("  ", problem)
            return 1
        print(f"schema mirrors in sync with schemas/ ({len(source_files)} files x {len(MIRRORS)} mirrors)")
        return 0

    if problems:
        for mirror in MIRRORS:
            for name, data in source_files.items():
                target = mirror / name
                if not target.is_file() or target.read_bytes() != data:
                    target.write_bytes(data)
                    print(f"synced: {target.relative_to(REPO)}")
        return 0
    print("already in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
