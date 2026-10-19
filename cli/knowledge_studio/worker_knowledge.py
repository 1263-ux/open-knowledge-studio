"""Read-only Worker field projection; optional Feishu transport stays outside core."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from knowledge_studio.knowledge_policy import DOMAIN_LABELS
from knowledge_studio.worker_records import DISPLAY_FIELDS, cell_text, clean_fields, clean_records, merge_records











def is_skill(meta: dict) -> bool:
    package = meta.get("skill_package")
    return (meta.get("artifact_kind") == "skill" or (isinstance(package, str) and bool(package.strip()))
            or meta.get("skill_candidate") is True
            or str(meta.get("skill_candidate") or "").lower() in {"true", "1", "yes"})


def _has_review_timestamp(meta: dict) -> bool:
    value = meta.get("human_reviewed_at")
    if not value:
        return False
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _path(root: Path, value: str) -> str:
    if not value or len(value) > 4096 or value.startswith(("//", "\\\\")) or "://" in value or "\n" in value:
        return ""
    try:
        path = (root / value).resolve()
        if path.is_relative_to(root.resolve()):
            return path.relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        pass
    return ""


def project(root: Path, points: list[dict], metadata: dict[str, dict], snapshot: dict | None = None) -> dict:
    """Attach facts by exact path or fully scoped source ID; never by title."""
    root = Path(root).resolve()
    snapshot = snapshot or {"state": "unconfigured", "records": []}
    source = {key: str((snapshot.get("source") or {}).get(key) or "") for key in ("base_token_hash", "table_id")}
    current = []
    by_path: dict[str, list] = {}
    by_source = {}
    for row in snapshot.get("records", []):
        if not isinstance(row, dict):
            continue
        record = {"source": {**source, "record_id": row.get("record_id")},
                  "fields": row.get("fields", {}), "observed_at": snapshot.get("observed_at", "")}
        clean = clean_records([record])
        if not clean:
            continue
        record = clean[0]
        record["state"] = snapshot.get("state", "unknown")
        record["linked_paths"] = []
        current.append(record)
        by_source[tuple(record["source"].values())] = record
        path = _path(root, record["fields"].get("Wiki路径", ""))
        if path:
            by_path.setdefault(path, []).append(record)
        candidate_id = record["fields"].get("候选ID", "")
        if re.fullmatch(r"[a-z0-9-]+", candidate_id):
            by_path.setdefault(f"drafts/{candidate_id}.md", []).append(record)
    capture_cache = {}
    for point in points:
        meta = metadata[point["id"]]
        records = clean_records(meta.get("worker_records"))
        references = [r["source"] for r in records]
        for trace in meta.get("traces", []) if isinstance(meta.get("traces"), list) else []:
            if not isinstance(trace, dict):
                continue
            run_id = str(trace.get("id") or "")
            if not re.fullmatch(r"run-[a-zA-Z0-9_-]+", run_id):
                continue
            if run_id not in capture_cache:
                file = (root / ".oks" / "runs" / run_id / "capture-envelope.json").resolve()
                try:
                    if not file.is_relative_to(root) or file.stat().st_size > 2_000_000:
                        continue
                    decoded = json.loads(file.read_text(encoding="utf-8"))
                    capture_cache[run_id] = decoded if isinstance(decoded, dict) else {}
                except (OSError, ValueError):
                    capture_cache[run_id] = {}
            capture = capture_cache.get(run_id, {})
            ref = capture.get("source_record") or {}
            if isinstance(ref, dict):
                references.append(ref)
                captured = clean_records([{"source": ref, "fields": capture.get("intake_fields", {}),
                                           "observed_at": capture.get("captured_at", "")}])
                records = merge_records(records, captured)
                sidecar = root / ".oks" / "runs" / run_id / "intake-fields.json"
                try:
                    if sidecar.resolve().is_relative_to(root) and sidecar.stat().st_size <= 2_000_000:
                        recorded = json.loads(sidecar.read_text(encoding="utf-8"))
                        valid = [r for r in clean_records([recorded]) if r["source"] == {
                            key: str(ref.get(key) or "") for key in ("base_token_hash", "table_id", "record_id")}]
                        records = merge_records(records, valid)
                except (OSError, ValueError):
                    pass
        linked = list(by_path.get(point["id"], []))
        for ref in references:
            key = tuple(str(ref.get(k) or "") for k in ("base_token_hash", "table_id", "record_id"))
            if key in by_source and by_source[key] not in linked:
                linked.append(by_source[key])
        for record in linked:
            record["linked_paths"].append(point["id"])
        live_keys = {tuple(r["source"].values()) for r in linked}
        records = [r for r in records if tuple(r["source"].values()) not in live_keys] + linked
        domains = []
        raw_domains = []
        for record in records:
            for value in re.split(r"[,，\n]", record["fields"].get("知识域", "")):
                value = value.strip()
                if value and value not in raw_domains:
                    raw_domains.append(value)
        source_domains = list(raw_domains)
        reviewed_classification = meta.get("classification_version") == 1 and _has_review_timestamp(meta)
        classification_source = "人工审核的知识域" if reviewed_classification else ("worker 知识域" if raw_domains else "本地 area（非飞书字段）")
        if reviewed_classification:
            raw_domains = [point["area"]] if point["area"] != "未分类" else []
        elif not raw_domains and point["area"] != "未分类":
            raw_domains = [point["area"]]
        for value in raw_domains:
            if value in DOMAIN_LABELS:
                domains.append({"id": value, "label": DOMAIN_LABELS[value]})
        point["is_skill"] = is_skill(meta)
        point["knowledge_domains"] = domains or [{"id": "_unmapped", "label": "待对齐知识域"}]
        point["classification"] = {"source": classification_source, "raw_values": raw_domains,
                                   "unmapped": [v for v in raw_domains if v not in DOMAIN_LABELS],
                                   "source_values": source_domains,
                                   "source_disagrees": reviewed_classification and bool(source_domains) and set(source_domains) != set(raw_domains)}
        point["worker_records"] = [{k: v for k, v in r.items() if k != "linked_paths"} for r in records]
    # Only records explicitly associated with visible points acquire linked paths.
    return {"state": snapshot.get("state", "unconfigured"), "observed_at": snapshot.get("observed_at", ""),
            "origin": snapshot.get("origin") if snapshot.get("origin") in {"fixture", "feishu", "local"} else ("feishu" if snapshot.get("state") != "unconfigured" else "local"),
            "partial": bool(snapshot.get("partial")), "missing_fields": snapshot.get("missing_fields", []),
            "error_code": snapshot.get("error_code", ""), "source": source,
            "records": current, "records_count": len(current),
            "linked_records": sum(bool(r["linked_paths"]) for r in current),
            "field_names": list(DISPLAY_FIELDS), "domain_options": DOMAIN_LABELS}
