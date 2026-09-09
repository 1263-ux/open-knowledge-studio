#!/usr/bin/env python3
"""Validate OKS DOCX package structure and Word table invariants."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import zipfile
import xml.etree.ElementTree as ET


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _attr(node: ET.Element, name: str) -> str | None:
    return node.get(f"{{{NS['w']}}}{name}")


def validate_docx(path: Path) -> dict:
    failures: list[str] = []
    with zipfile.ZipFile(path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            failures.append(f"corrupt zip member: {bad_member}")
        try:
            root = ET.fromstring(archive.read("word/document.xml"))
        except KeyError as exc:
            failures.append(f"missing word/document.xml: {exc}")
            return {"valid": False, "failures": failures}
    tables = root.findall(".//w:tbl", NS)
    for index, table in enumerate(tables):
        layout = table.find("./w:tblPr/w:tblLayout", NS)
        if layout is None or _attr(layout, "type") != "fixed":
            failures.append(f"tables[{index}] must use fixed layout")
        rows = table.findall("./w:tr", NS)
        if not rows:
            failures.append(f"tables[{index}] has no rows")
            continue
        header = rows[0].find("./w:trPr/w:tblHeader", NS)
        if header is None:
            failures.append(f"tables[{index}] first row must repeat as header")
        header_cells = rows[0].findall("./w:tc", NS)
        for cell_index, cell in enumerate(header_cells):
            width = cell.find("./w:tcPr/w:tcW", NS)
            shading = cell.find("./w:tcPr/w:shd", NS)
            if width is None or _attr(width, "type") != "dxa":
                failures.append(f"tables[{index}].header[{cell_index}] missing dxa width")
            if shading is None or not _attr(shading, "fill"):
                failures.append(f"tables[{index}].header[{cell_index}] missing shading")
    return {"valid": not failures, "tables": len(tables), "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = validate_docx(args.input)
    except (OSError, zipfile.BadZipFile, ET.ParseError) as exc:
        result = {"valid": False, "failures": [str(exc)]}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
