#!/usr/bin/env python3
"""Check an OKS Office package and the local adapter dependencies."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from evidence_package import load_package, package_to_outline


def _has_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--format", action="append", choices=("docx", "pdf", "pptx", "xlsx"), dest="formats")
    parser.add_argument("--font-path", type=Path)
    args = parser.parse_args()
    formats = args.formats or ["docx", "pdf", "pptx", "xlsx"]
    try:
        package = load_package(args.package)
        outline = package_to_outline(package)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ready": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    text_blob = json.dumps(outline, ensure_ascii=False)
    checks: dict[str, object] = {"evidence_package": "pass", "formats": {}}
    failures: list[str] = []
    for fmt, module in (("docx", "docx"), ("pdf", "reportlab"), ("pptx", "pptx"), ("xlsx", "openpyxl")):
        if fmt not in formats:
            continue
        available = _has_module(module)
        entry: dict[str, object] = {"dependency": module, "available": available}
        if not available:
            failures.append(f"{fmt} dependency unavailable: {module}")
        if fmt == "pdf" and any("\u2e80" <= char <= "\u9fff" or "\uf900" <= char <= "\ufaff" or "\uff00" <= char <= "\uffef" for char in text_blob):
            has_font = bool(args.font_path and args.font_path.is_file())
            entry["cjk_font"] = has_font
            if not has_font:
                failures.append("pdf CJK content requires an existing --font-path")
        checks["formats"][fmt] = entry  # type: ignore[index]
    checks["ready"] = not failures
    if failures:
        checks["failures"] = failures
    print(json.dumps(checks, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
