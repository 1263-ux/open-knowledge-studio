#!/usr/bin/env python3
"""Run an installed OKS hook with the package root supplied by the installer."""
from __future__ import annotations

import runpy
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: _hook_runner.py <hook-script> <package-root>", file=sys.stderr)
        return 2
    hook_script = sys.argv[1]
    package_root = sys.argv[2]
    if package_root and package_root not in sys.path:
        sys.path.insert(0, package_root)
    runpy.run_path(hook_script, run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
