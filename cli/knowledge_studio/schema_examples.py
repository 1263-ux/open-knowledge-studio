"""Minimal-valid examples for every OKS protocol schema.

Each function returns a ``dict`` that passes the corresponding schema's
own JSON Schema validation.  Used by ``oks schema example <name>`` so
Agents can see the exact shape of a valid document without guessing.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

# Stable sample hash for examples (64 hex chars, all-zero is invalid for
# actual content but fine as a placeholder).
_SAMPLE_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
_SAMPLE_ID = f"src-{uuid.uuid4().hex[:12]}"
_SAMPLE_MANIFEST_ID = f"manifest-{uuid.uuid4().hex[:12]}"
_SAMPLE_FRAGMENT_ID = f"frag-{uuid.uuid4().hex[:12]}"
_SAMPLE_ARTIFACT_ID = f"art-{uuid.uuid4().hex[:12]}"
_SAMPLE_TS = datetime.now(timezone.utc).isoformat()


def source_envelope() -> dict[str, Any]:
    return {
        "schema_version": "oks-source-envelope/v0.1",
        "source_id": _SAMPLE_ID,
        "source_uri": "file:///tmp/example.md",
        "source_modality": "text",
        "access_mode": "local_file",
        "captured_at": _SAMPLE_TS,
        "captured_by": {
            "runtime": "claude-code",
            "model": None,
            "skill": "ingest",
        },
        "content_hash": _SAMPLE_HASH,
        "evidence_manifest_ref": _SAMPLE_MANIFEST_ID,
        "title": "Example Source",
        "user_note": None,
    }


def evidence_manifest() -> dict[str, Any]:
    return {
        "schema_version": "oks-evidence-manifest/v0.1",
        "manifest_id": _SAMPLE_MANIFEST_ID,
        "source_id": _SAMPLE_ID,
        "status": "complete",
        "fragment_refs": [_SAMPLE_FRAGMENT_ID],
        "primary_artifact": {
            "artifact_id": _SAMPLE_ARTIFACT_ID,
            "kind": "primary_text",
            "path": "content.md",
            "media_type": "text/markdown",
            "sha256": _SAMPLE_HASH,
            "locator_kind": "document",
        },
        "evidence_records": [
            {
                "evidence_id": f"ev-{uuid.uuid4().hex[:12]}",
                "artifact_id": _SAMPLE_ARTIFACT_ID,
                "kind": "text_content",
                "method": "text-read",
                "locator": {"kind": "document"},
                "text": "Sample evidence text content.",
                "confidence": 1.0,
                "agent_judgment": "mechanical",
            }
        ],
        "modalities": {
            "text": {
                "modality": "text",
                "status": "succeeded",
                "evidence_count": 1,
                "error_code": None,
            }
        },
        "provenance": {
            "agent": {
                "runtime": "claude-code",
                "model": None,
                "skill": "ingest",
            },
            "latency_ms": 0,
        },
        "steps": [
            {
                "capability": "document.text.extract",
                "provider": "text-read",
                "status": "succeeded",
                "reason": None,
            }
        ],
        "notes": {},
    }


def evidence_fragment() -> dict[str, Any]:
    return {
        "schema_version": "oks-evidence-fragment/v0.1",
        "fragment_id": _SAMPLE_FRAGMENT_ID,
        "source_id": _SAMPLE_ID,
        "producer": {
            "runtime": "oks",
            "provider": "text-read",
            "tool": "agent-runtime",
        },
        "status": "succeeded",
        "artifacts": [
            {
                "artifact_id": _SAMPLE_ARTIFACT_ID,
                "kind": "primary_text",
                "path": "content.md",
                "sha256": _SAMPLE_HASH,
            }
        ],
        "evidence": [
            {
                "evidence_id": f"ev-{uuid.uuid4().hex[:12]}",
                "artifact_id": _SAMPLE_ARTIFACT_ID,
                "kind": "text_content",
                "method": "text-read",
                "locator": {"kind": "document"},
                "confidence": 1.0,
            }
        ],
        "modalities": {
            "text": {
                "modality": "text",
                "status": "succeeded",
                "evidence_count": 1,
            }
        },
        "agent_notes": None,
    }


def locator() -> dict[str, Any]:
    return {"kind": "document", "document_section": "body"}


def raw_bundle() -> dict[str, Any]:
    """Mirror the document ``_assemble_bundle`` writes to ``bundle.json``."""
    return {
        "schema_version": "raw-multimodal/v0.2",
        "bundle_id": f"bundle:{_SAMPLE_HASH[:16]}",
        "capture_id": _SAMPLE_ID,
        "content_hash": _SAMPLE_HASH,
        "recipe_version": "oks-agent-native-ingest/v0.1",
        "processing_status": "complete",
        "files": {
            "manifest": "bundle.json",
            "content": "content.md",
            "evidence": "evidence.jsonl",
            "quality_report": "quality-report.json",
            "processing_runs": "processing-runs.jsonl",
            "source_dir": "source/",
            "assets_dir": "assets/",
            "derived_dir": "derived/",
        },
        "sources": [
            {
                "entity_id": _SAMPLE_ARTIFACT_ID,
                "path": "source/content.md",
                "sha256": _SAMPLE_HASH,
                "media_type": "text/markdown",
                "snapshot_kind": "content",
                "content_hash_status": "verified",
                "primary_source": True,
            }
        ],
        "derived": [],
        "provenance": {
            "entities": [{"id": _SAMPLE_ARTIFACT_ID, "kind": "primary_text"}],
            "activities": [
                {"id": f"run-{uuid.uuid4().hex[:12]}", "kind": "ingest", "ended_at": _SAMPLE_TS}
            ],
            "agents": [{"id": "claude-code", "kind": "agent-runtime"}],
            "relations": [
                {
                    "type": "wasGeneratedBy",
                    "subject": _SAMPLE_ARTIFACT_ID,
                    "object": _SAMPLE_MANIFEST_ID,
                }
            ],
        },
        "warnings": [],
    }


_SCHEMA_EXAMPLES: dict[str, dict[str, Any]] = {
    "source-envelope": source_envelope(),
    "evidence-manifest": evidence_manifest(),
    "evidence-fragment": evidence_fragment(),
    "locator": locator(),
    "raw-bundle": raw_bundle(),
}


def get_example(name: str) -> dict[str, Any] | None:
    """Return a minimal valid example for schema *name*, or None."""
    return _SCHEMA_EXAMPLES.get(name)


def list_schema_names() -> list[str]:
    """Return the short names of all available schemas."""
    return sorted(_SCHEMA_EXAMPLES.keys())
