"""Shared utilities used by raw_bundle_adapter and extractor modules.

These are pure functions with no side-effects on the extraction pipeline.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable


# ── I/O helpers ───────────────────────────────────────────────────

def emit_json(value: Any, *, indent: int | None = None) -> None:
    """Write UTF-8 JSON without depending on the Windows console code page."""
    payload = json.dumps(value, ensure_ascii=False, indent=indent) + "\n"
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        buffer.write(payload.encode("utf-8"))
        buffer.flush()
        return
    sys.stdout.write(payload)
    sys.stdout.flush()


def emit_progress(enabled: bool, phase: str, fraction: float, eta_seconds: int | None) -> None:
    """Emit machine-readable progress on stderr without corrupting CLI JSON output."""
    if not enabled:
        return
    payload = {
        "event": "progress",
        "phase": phase,
        "percent": round(max(0.0, min(1.0, fraction)) * 100, 1),
        "estimated_remaining_seconds": eta_seconds,
    }
    sys.stderr.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stderr.flush()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False) + "\n")
            count += 1
    return count


def exactly_one(root: Path, pattern: str) -> Path:
    matches = sorted(root.rglob(pattern))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {pattern!r} under {root}, found {len(matches)}")
    return matches[0]


def prepare_output(path: Path, overwrite: bool) -> Path:
    path = path.expanduser().resolve()
    if path.exists():
        if not overwrite:
            raise FileExistsError(f"output already exists: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


# ── OCR helpers ────────────────────────────────────────────────────

def normalize_ocr_text(value: str) -> str:
    return " ".join(value.split())


def order_ocr_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort OCR blocks by reading order (top-to-bottom, left-to-right)."""
    indexed = [(i, item) for i, item in enumerate(blocks)]
    indexed.sort(key=lambda item: (
        round(item[1].get("bbox", [0, 0, 0, 0])[1], 1),
        round(item[1].get("bbox", [0, 0, 0, 0])[0], 1),
    ))
    return [{**item, "source_index": i} for i, (orig_i, item) in enumerate(indexed)]


def parse_ocr_roi(raw: str | None) -> tuple[int, int, int, int] | None:
    """Parse an OCR ROI string ``x1,y1,x2,y2``, or return None."""
    if not raw or not raw.strip():
        return None
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        raise ValueError(f"OCR ROI must be x1,y1,x2,y2, got: {raw!r}")
    coords = tuple(int(p) for p in parts)
    if coords[0] >= coords[2] or coords[1] >= coords[3]:
        raise ValueError(f"OCR ROI must have x1<x2 and y1<y2, got: {raw!r}")
    return coords  # type: ignore[return-value]


def format_media_time(seconds: float) -> str:
    """Format seconds as mm:ss."""
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"
