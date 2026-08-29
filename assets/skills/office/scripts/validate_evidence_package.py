#!/usr/bin/env python3
"""Fail-closed validator for an OKS Office evidence package."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from evidence_package import load_package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        package = load_package(args.package)
        result = {
            "valid": True,
            "schema_version": package["schema_version"],
            "claims": len(package["claims"]),
            "sections": len(package["sections"]),
            "sources": len(package["sources"]),
        }
        print(json.dumps(result, ensure_ascii=False) if args.as_json else "valid OKS Office evidence package")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"valid": False, "error": str(exc)}
        print(json.dumps(result, ensure_ascii=False) if args.as_json else f"invalid: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
