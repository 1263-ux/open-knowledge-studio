"""Optional read-only Studio source. No claims, upserts, messages or writes."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import threading
import time
from datetime import datetime, timezone

from feishu_worker.base_client import _parse_record_rows, base_args

# Keep in parity with the packaged core projection (tested across the boundary).
DISPLAY_FIELDS = ("知识域", "评级", "总结", "思考", "重点问题（可选）", "Wiki状态", "质量状态",
                  "审核动作", "审核时间", "审核意见", "运行状态", "采集模式", "状态", "内容",
                  "Raw Bundle", "Wiki路径", "运行ID", "候选ID", "错误码", "错误说明")


def source_identity(config, record_id=""):
    source = {"base_token_hash": hashlib.sha256(config.base_token.encode()).hexdigest()[:12],
              "table_id": config.table_id}
    if record_id:
        source["record_id"] = record_id
    return source


def snapshot_record(config, record_id, fields):
    return {"source": source_identity(config, record_id),
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "fields": {key: fields[key] for key in DISPLAY_FIELDS if key in fields}}


def merge_observation(previous, current):
    """Preserve other sources when recording a newly read Worker observation.

    This optional adapter keeps raw cell values without requiring the core CLI
    package before human promotion. The core normalizes cells when storing Wiki.
    """
    merged = {}
    for row in (previous if isinstance(previous, list) else []) + [current]:
        if not isinstance(row, dict) or not isinstance(row.get("source"), dict):
            continue
        source = {key: str(row["source"].get(key) or "") for key in ("base_token_hash", "table_id", "record_id")}
        if not all(source.values()):
            continue
        key = tuple(source.values())
        fields = row.get("fields") if isinstance(row.get("fields"), dict) else {}
        fields = {name: fields[name] for name in DISPLAY_FIELDS if name in fields}
        merged[key] = {"source": source, "observed_at": str(row.get("observed_at") or ""),
                       "fields": {**merged.get(key, {}).get("fields", {}), **fields}}
    return list(merged.values())


def _read_only_json(config, *args, root):
    if args[:2] not in (("base", "+field-list"), ("base", "+record-list")):
        raise ValueError("The knowledge reader only allows field-list and record-list")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", config.base_token) or not re.fullmatch(r"tbl[A-Za-z0-9]+", config.table_id):
        raise ValueError("Knowledge reader requires Base and table IDs")
    result = subprocess.run([str(config.lark_cli), *args], cwd=root, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=10)
    value = json.loads(result.stdout)
    if result.returncode or not isinstance(value, dict) or value.get("ok") is not True:
        raise RuntimeError("Feishu read was not successful")
    return value


class KnowledgeReader:
    """Bounded paginated pull with an in-memory, explicitly stale fallback."""
    def __init__(self, config, root, *, call=None, ttl=30, max_records=2000):
        self.config, self.root = config, root
        self.call = call or _read_only_json
        self.ttl, self.max_records = ttl, max_records
        self.lock = threading.Lock()
        self.cached = None
        self.checked = 0.0

    def snapshot(self, *, force=False):
        with self.lock:
            if not force and self.cached is not None and time.monotonic() - self.checked < self.ttl:
                return self.cached
            try:
                value = self._read()
            except Exception:
                # Transport diagnostics may include credentials; expose only a
                # stable error code. The original success time is never renewed.
                value = {**(self.cached or {}), "state": "stale" if self.cached and self.cached.get("observed_at") else "error",
                         "error_code": "FEISHU_READ_FAILED", "source": source_identity(self.config)}
                value.setdefault("records", [])
            self.cached = value
            self.checked = time.monotonic()
            return value

    def _read(self):
        started = time.monotonic()
        raw = self.call(self.config, "base", "+field-list", *base_args(self.config), "--format", "json", root=self.root)
        data = raw.get("data") or {}
        fields = data.get("fields", [])
        names = {str(f.get("name") or f.get("field_name") or "") for f in fields}
        available = [name for name in DISPLAY_FIELDS if name in names]
        aliases = {"希望解决的问题": "重点问题（可选）"} if "重点问题（可选）" not in names and "希望解决的问题" in names else {}
        requested = available + list(aliases)
        if not requested:
            raise ValueError("No known Worker fields")
        records = []
        offset = 0
        seen = set()
        partial = False
        while True:
            if time.monotonic() - started > 30:
                raise TimeoutError("Worker snapshot exceeded its read budget")
            size = min(200, self.max_records - len(records))
            if size <= 0:
                partial = True
                break
            args = ["base", "+record-list", *base_args(self.config), "--limit", str(size), "--offset", str(offset), "--format", "json"]
            for name in requested:
                args.extend(["--field-id", name])
            envelope = self.call(self.config, *args, root=self.root)
            data = envelope.get("data") or {}
            rows = data.get("data", [])
            resolved = _parse_record_rows(rows, data.get("fields", requested), data.get("record_id_list", []))
            added = 0
            for row in resolved:
                if row["record_id"] in seen:
                    continue
                seen.add(row["record_id"])
                fields = dict(row["fields"])
                for old, new in aliases.items():
                    fields[new] = fields.pop(old, "")
                records.append({"record_id": row["record_id"], "fields": {key: fields[key] for key in DISPLAY_FIELDS if key in fields}})
                added += 1
            total = data.get("total")
            has_more = data.get("has_more")
            if has_more is False or (isinstance(total, int) and offset + len(rows) >= total) or (has_more is None and len(rows) < size):
                break
            if not rows or not added:
                raise ValueError("Pagination did not advance")
            offset += len(rows)
        return {"schema": "oks.worker-knowledge.v1", "state": "live", "source": source_identity(self.config),
                "observed_at": datetime.now(timezone.utc).isoformat(), "records": records, "partial": partial,
                "missing_fields": [name for name in DISPLAY_FIELDS if name not in available and name not in aliases.values()]}
