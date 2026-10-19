"""Sanitized, source-scoped observations from the optional Worker adapter."""
from __future__ import annotations

from datetime import datetime, timezone

DISPLAY_FIELDS = (
    "知识域", "评级", "总结", "思考", "重点问题（可选）", "Wiki状态", "质量状态",
    "审核动作", "审核时间", "审核意见", "运行状态", "采集模式", "状态", "内容",
    "Raw Bundle", "Wiki路径", "运行ID", "候选ID", "错误码", "错误说明",
)


def cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        if all(isinstance(item, dict) and "text" in item for item in value):
            return "".join(cell_text(item) for item in value)
        return ", ".join(filter(None, (cell_text(item) for item in value)))
    if isinstance(value, dict):
        for key in ("text", "name", "value"):
            if key in value:
                return cell_text(value[key])
    return ""


def clean_fields(fields: dict) -> dict:
    """Project known display fields, never credentials, attachments or leases."""
    if not isinstance(fields, dict):
        return {}
    fields = dict(fields)
    if "重点问题（可选）" not in fields and "希望解决的问题" in fields:
        fields["重点问题（可选）"] = fields["希望解决的问题"]
    return {key: cell_text(fields[key]) for key in DISPLAY_FIELDS if key in fields}


def clean_records(records) -> list[dict]:
    result = []
    if not isinstance(records, list):
        return result
    for row in records:
        if not isinstance(row, dict):
            continue
        source = row.get("source") or {}
        if not isinstance(source, dict):
            continue
        safe = {key: str(source.get(key) or "") for key in ("base_token_hash", "table_id", "record_id")}
        if not all(safe.values()):
            continue
        result.append({"source": safe, "observed_at": str(row.get("observed_at") or ""),
                       "fields": clean_fields(row.get("fields") or {}), "state": "snapshot"})
    return result


def merge_records(previous, incoming) -> list[dict]:
    def observed(row):
        try:
            value = datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00"))
            return value.replace(tzinfo=value.tzinfo or timezone.utc).timestamp()
        except (TypeError, ValueError):
            return float("-inf")

    merged = {}
    for row in clean_records(previous) + clean_records(incoming):
        key = tuple(row["source"].values())
        if key not in merged or observed(row) >= observed(merged[key]):
            if key in merged:
                row["fields"] = {**merged[key]["fields"], **row["fields"]}
            merged[key] = row
    return list(merged.values())
