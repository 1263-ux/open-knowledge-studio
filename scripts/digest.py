"""Auto-generate Agent-friendly digest and index after each ingest."""

from __future__ import annotations

import json
from pathlib import Path


def write_digest(bundle: Path) -> None:
    """Generate digest.md inside the bundle for Agent quick-scan."""
    qr_path = bundle / "quality-report.json"
    meta_path = bundle / "metadata.json"
    if not qr_path.is_file() or not meta_path.is_file():
        return
    qr = json.loads(qr_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    source_info = meta.get("source", {})
    title = source_info.get("title") or bundle.name
    source = source_info.get("url") or source_info.get("local_path", "unknown")
    modality = meta.get("source_type", "unknown")
    status = qr.get("processing_status", meta.get("processing_status", "unknown"))
    transcript_n = qr.get("transcript_segment_count", 0)
    frame_n = qr.get("frame_count", 0)
    ocr_n = qr.get("ocr_block_count", 0)
    evidence_n = qr.get("evidence_count", 0)
    warnings = [w for w in qr.get("warnings", []) if w]
    human = qr.get("human_fallback", "")
    lines = [
        f"# {title}",
        f"- 来源：{source}",
        f"- 模态：{modality}",
        f"- 状态：{status}",
        f"- 证据：字幕{transcript_n}段 / 帧{frame_n} / OCR{ocr_n}块 / 总计{evidence_n}条",
    ]
    if warnings:
        lines.append(f"- 警告：{'；'.join(warnings)}")
    if human:
        lines.append(f"- 人工核验建议：{human}")
    lines.append("")
    (bundle / "digest.md").write_text("\n".join(lines), encoding="utf-8")


def update_raw_index(bundle: Path) -> None:
    """Append this bundle's entry to raw/index.json."""
    raw_dir = bundle.parent
    index_path = raw_dir / "index.json"
    entries: list[dict] = []
    if index_path.is_file():
        try:
            entries = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = []
    qr_path = bundle / "quality-report.json"
    meta_path = bundle / "metadata.json"
    if not qr_path.is_file() or not meta_path.is_file():
        return
    qr = json.loads(qr_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    source_info = meta.get("source", {})
    bundle_id = bundle.name
    existing = {e["id"] for e in entries if "id" in e}
    if bundle_id in existing:
        return
    entries.append({
        "id": bundle_id,
        "source": source_info.get("url") or source_info.get("local_path", ""),
        "title": source_info.get("title", ""),
        "modality": meta.get("source_type", ""),
        "collected_at": source_info.get("collected_at", ""),
        "status": qr.get("processing_status", meta.get("processing_status", "")),
        "digest": f"raw/{bundle_id}/digest.md",
        "evidence_count": qr.get("evidence_count", 0),
        "warnings": [w for w in qr.get("warnings", []) if w],
    })
    index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
