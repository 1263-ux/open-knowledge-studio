#!/usr/bin/env python3
"""Validate and normalize an OKS Office evidence package.

The package is the bridge between OKS recall and format adapters. It keeps
claim-to-source mappings explicit, then produces the older shared outline
shape so existing renderers remain compatible.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SOURCE_STATUSES = {
    "reviewed",
    "partial",
    "failed",
    "skipped",
    "environment_limited",
    "unverified",
    "synthesis",
}
SOURCE_KINDS = {"wiki", "raw", "profile", "web", "research", "template", "synthesis"}
EXTERNAL_SOURCE_KINDS = {"web", "research"}
CLAIM_STATUSES = {"reviewed", "provisional", "unverified"}
CONFIDENCES = {"high", "medium", "low"}
BLOCK_TYPES = {"paragraph", "bullets", "table", "callout"}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _refs(value: Any, location: str) -> list[str]:
    if not isinstance(value, list) or not value or any(not _text(item) for item in value):
        raise ValueError(f"{location} must be a non-empty list of ids")
    return [_text(item) for item in value]


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_timestamp(value: str) -> bool:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def load_package(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_package(data)
    return data
def validate_package(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("evidence package must be a JSON object")
    if data.get("schema_version") != "oks-office-evidence/v1":
        raise ValueError("schema_version must be oks-office-evidence/v1")
    request = data.get("request")
    if not isinstance(request, dict) or not _text(request.get("title")):
        raise ValueError("request.title is required")
    recall = data.get("recall")
    if not isinstance(recall, dict) or not _text(recall.get("query")):
        raise ValueError("recall.query is required after the fixed research step")

    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("sources must be a non-empty list")
    source_ids: set[str] = set()
    for index, source in enumerate(sources):
        location = f"sources[{index}]"
        if not isinstance(source, dict):
            raise ValueError(f"{location} must be an object")
        source_id = _text(source.get("id"))
        kind = _text(source.get("kind"))
        label = _text(source.get("label"))
        locator = _text(source.get("locator"))
        status = _text(source.get("status"))
        if not source_id or not kind or not label or not locator:
            raise ValueError(f"{location} requires id, kind, label, and locator")
        if source_id in source_ids:
            raise ValueError(f"duplicate source id: {source_id}")
        if kind not in SOURCE_KINDS:
            raise ValueError(f"{location}.kind must be one of {sorted(SOURCE_KINDS)}")
        if status not in SOURCE_STATUSES:
            raise ValueError(f"{location}.status must be one of {sorted(SOURCE_STATUSES)}")
        if kind in EXTERNAL_SOURCE_KINDS:
            if not _is_http_url(locator):
                raise ValueError(f"{location}.locator must be an http(s) URL for external research")
            retrieved_at = _text(source.get("retrieved_at"))
            if not _is_timestamp(retrieved_at):
                raise ValueError(f"{location}.retrieved_at must be an ISO 8601 timestamp with a timezone")
            if status == "reviewed":
                raise ValueError(f"{location}.status cannot be reviewed for direct external research")
        source_ids.add(source_id)

    if not any(_text(source.get("kind")) in EXTERNAL_SOURCE_KINDS for source in sources):
        raise ValueError("sources must include one web or research source from the fixed research step")

    claims = data.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ValueError("claims must be a non-empty list")
    claim_ids: set[str] = set()
    for index, claim in enumerate(claims):
        location = f"claims[{index}]"
        if not isinstance(claim, dict):
            raise ValueError(f"{location} must be an object")
        claim_id = _text(claim.get("id"))
        if not claim_id or not _text(claim.get("text")):
            raise ValueError(f"{location} requires id and text")
        if claim_id in claim_ids:
            raise ValueError(f"duplicate claim id: {claim_id}")
        source_refs = _refs(claim.get("source_refs"), f"{location}.source_refs")
        unknown = [ref for ref in source_refs if ref not in source_ids]
        if unknown:
            raise ValueError(f"{location}.source_refs contains unknown ids: {unknown}")
        review_status = _text(claim.get("review_status"))
        if review_status not in CLAIM_STATUSES:
            raise ValueError(f"{location}.review_status must be one of {sorted(CLAIM_STATUSES)}")
        if review_status == "reviewed" and any(
            _text(source["kind"]) in EXTERNAL_SOURCE_KINDS
            for source in sources
            if _text(source["id"]) in source_refs
        ):
            raise ValueError(f"{location}.review_status cannot be reviewed when based on direct external research")
        confidence = _text(claim.get("confidence"))
        if confidence and confidence not in CONFIDENCES:
            raise ValueError(f"{location}.confidence must be one of {sorted(CONFIDENCES)}")
        claim_ids.add(claim_id)

    def check_claim_refs(value: Any, location: str) -> list[str]:
        refs = _refs(value, location)
        unknown = [ref for ref in refs if ref not in claim_ids]
        if unknown:
            raise ValueError(f"{location} contains unknown claim ids: {unknown}")
        return refs

    summary = data.get("summary")
    if summary is not None:
        if not isinstance(summary, dict) or not _text(summary.get("text")):
            raise ValueError("summary requires text and claim_refs")
        check_claim_refs(summary.get("claim_refs"), "summary.claim_refs")

    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("sections must be a non-empty list")
    section_ids: set[str] = set()
    for section_index, section in enumerate(sections):
        location = f"sections[{section_index}]"
        if not isinstance(section, dict):
            raise ValueError(f"{location} must be an object")
        section_id = _text(section.get("id"))
        if not section_id or section_id in section_ids:
            raise ValueError(f"{location}.id is required and must be unique")
        section_claims = set(check_claim_refs(section.get("claim_refs"), f"{location}.claim_refs"))
        blocks = section.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            raise ValueError(f"{location}.blocks must be a non-empty list")
        for block_index, block in enumerate(blocks):
            block_location = f"{location}.blocks[{block_index}]"
            if not isinstance(block, dict):
                raise ValueError(f"{block_location} must be an object")
            block_type = _text(block.get("type"))
            if block_type not in BLOCK_TYPES:
                raise ValueError(f"{block_location}.type must be one of {sorted(BLOCK_TYPES)}")
            block_claims = set(check_claim_refs(block.get("claim_refs"), f"{block_location}.claim_refs"))
            if not block_claims.issubset(section_claims):
                raise ValueError(f"{block_location}.claim_refs must be a subset of its section claim_refs")
            if block_type in {"paragraph", "callout"} and not _text(block.get("text")):
                raise ValueError(f"{block_location}.text is required")
            if block_type == "bullets":
                items = block.get("items")
                if not isinstance(items, list) or not items:
                    raise ValueError(f"{block_location}.items must be a non-empty list")
                for item_index, item in enumerate(items):
                    item_location = f"{block_location}.items[{item_index}]"
                    if isinstance(item, str):
                        if not item.strip():
                            raise ValueError(f"{item_location} cannot be empty")
                    elif isinstance(item, dict):
                        if not _text(item.get("text")):
                            raise ValueError(f"{item_location}.text is required")
                        item_claims = set(check_claim_refs(item.get("claim_refs"), f"{item_location}.claim_refs"))
                        if not item_claims.issubset(block_claims):
                            raise ValueError(f"{item_location}.claim_refs must be a subset of its block claim_refs")
                    else:
                        raise ValueError(f"{item_location} must be a string or object")
            if block_type == "table":
                rows = block.get("rows")
                if not isinstance(rows, list) or not rows or any(not isinstance(row, list) or not row for row in rows):
                    raise ValueError(f"{block_location}.rows must be a non-empty list of rows")
                width = len(rows[0])
                if any(len(row) != width for row in rows):
                    raise ValueError(f"{block_location}.rows must be rectangular")
        section_ids.add(section_id)
    return data
