"""``oks ingest prepare`` — generate protocol skeleton for Agent ingestion.

Core principle: the Agent should fill in *evidence content*, not protocol
plumbing.  This module handles source detection, workspace creation, and
protocol skeleton generation so the Agent never needs to hand-craft a
SourceEnvelope, EvidenceManifest, or EvidenceFragment.
"""

from __future__ import annotations

import json
import os as _os
import uuid
from datetime import datetime, timezone
from hashlib import sha256 as _sha256
from pathlib import Path
from typing import Any

from knowledge_studio.store import repo_root

# ── Source modality detection ──────────────────────────────────────

_MODALITY_MAP: dict[str, str] = {
    ".md": "text",
    ".txt": "text",
    ".csv": "text",
    ".json": "text",
    ".yaml": "text",
    ".yml": "text",
    ".pdf": "pdf",
    ".docx": "office",
    ".pptx": "office",
    ".xlsx": "office",
    ".html": "web",
    ".htm": "web",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".mp4": "video",
    ".mkv": "video",
    ".mov": "video",
    ".mp3": "audio",
    ".wav": "audio",
    ".flac": "audio",
}

_URL_PATTERNS: dict[str, str] = {
    "bilibili.com": "video",
    "youtube.com": "video",
    "youtu.be": "video",
    "douyin.com": "video",
}


def _detect_modality(source: str) -> str:
    """Detect source modality from file extension or URL pattern."""
    path = Path(source.split("?", 1)[0])
    suffix = path.suffix.lower()
    if suffix in _MODALITY_MAP:
        return _MODALITY_MAP[suffix]
    # Try URL patterns
    source_lower = source.lower()
    for domain, modality in _URL_PATTERNS.items():
        if domain in source_lower:
            return modality
    # Generic URL
    if source_lower.startswith(("http://", "https://")):
        return "web"
    return "text"


def _detect_access_mode(source: str) -> str:
    """Detect access mode from source string."""
    path = Path(source.split("?", 1)[0])
    if path.is_file() or path.exists():
        return "local_file"
    if source.startswith(("http://", "https://")):
        return "public_url"
    return "manual"


# ── prepare_ingest ─────────────────────────────────────────────────


def prepare_ingest(source: str, kb_root: Path | None = None) -> dict[str, Any]:
    """Create a run workspace and generate protocol skeleton for *source*.

    Returns a dict the CLI serializes to JSON:

    ```json
    {
      "run_id": "...",
      "workspace": "/path/to/.oks/runs/run-xxx/",
      "manifest_dir": "/path/to/.oks/runs/run-xxx/manifest/",
      "source": "...",
      "modality": "text",
      "source_id": "src-xxx",
      "content_hash": "sha256...",
      "files_generated": ["source-envelope.json", "evidence-manifest.json", ...],
      "next_step": "Fill evidence_records in evidence-manifest.json, then run: oks raw-commit ...",
      "text_ready": true   (only true when the scaffold includes pre-filled evidence)
    }
    ```
    """
    root = kb_root or Path(_os.environ.get("OKS_ROOT", repo_root()))
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    runs_dir = root / ".oks" / "runs" / run_id
    manifest_dir = runs_dir / "manifest"
    artifacts_dir = manifest_dir / "artifacts"
    fragments_dir = manifest_dir / "fragments"

    for d in [manifest_dir, artifacts_dir, fragments_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # ── Determine source metadata ──
    modality = _detect_modality(source)
    access_mode = _detect_access_mode(source)
    source_id = f"src-{uuid.uuid4().hex[:12]}"
    captured_at = datetime.now(timezone.utc).isoformat()
    is_text = modality == "text" and access_mode == "local_file"
    is_remote = access_mode == "public_url"

    # ── Read and hash (local files only) ──
    source_bytes = b""
    content_hash = ""
    if is_text:
        try:
            source_bytes = Path(source).read_bytes()
            content_hash = _sha256(source_bytes).hexdigest()
        except OSError:
            source_bytes = b""
            content_hash = ""

    if not content_hash:
        content_hash = _sha256(source.encode("utf-8")).hexdigest()

    # ── Build source-envelope.json ──
    envelope = {
        "schema_version": "oks-source-envelope/v0.1",
        "source_id": source_id,
        "source_uri": str(Path(source).resolve()) if access_mode == "local_file" else source,
        "source_modality": modality,
        "access_mode": access_mode,
        "captured_at": captured_at,
        "captured_by": {
            "runtime": "claude-code",
            "model": None,
            "skill": "ingest",
        },
        "content_hash": content_hash,
        "evidence_manifest_ref": f"manifest-{run_id}",
        "title": _title_from_source(source),
        "user_note": None,
        "policy": {
            "remote_processing": "allow" if is_remote else "deny",
            "sensitivity": "internal",
        },
    }

    # ── Build evidence-manifest.json skeleton ──
    manifest_id = f"manifest-{run_id}"
    fragment_id = f"frag-{uuid.uuid4().hex[:12]}"
    artifact_id = f"art-{uuid.uuid4().hex[:12]}"
    artifact_path = f"content{Path(source).suffix}" if is_text else "content.txt"

    manifest: dict[str, Any] = {
        "schema_version": "oks-evidence-manifest/v0.1",
        "manifest_id": manifest_id,
        "source_id": source_id,
        "status": "complete" if is_text else "partial",
        "fragment_refs": [fragment_id],
        "primary_artifact": {
            "artifact_id": artifact_id,
            "kind": "primary_text",
            "path": artifact_path,
            "media_type": _media_type(source),
            "sha256": content_hash,
            "locator_kind": "document",
        },
        "evidence_records": [],
        "modalities": {},
        "provenance": {
            "agent": {
                "runtime": "claude-code",
                "model": None,
                "skill": "ingest",
            },
            "latency_ms": None,
        },
        "steps": [],
        "notes": {},
    }

    # ── For text sources: pre-fill evidence ──
    text_ready = False
    if is_text and source_bytes:
        # Write artifact
        (artifacts_dir / artifact_path).write_bytes(source_bytes)

        # Pre-fill evidence record with text content
        text_content = source_bytes.decode("utf-8", errors="replace")
        manifest["evidence_records"] = [
            {
                "evidence_id": f"ev-{uuid.uuid4().hex[:12]}",
                "artifact_id": artifact_id,
                "kind": "text_content",
                "method": "text-read",
                "locator": {"kind": "document"},
                "text": text_content,
                "confidence": 1.0,
                "agent_judgment": "mechanical",
            }
        ]
        manifest["modalities"] = {
            "text": {
                "modality": "text",
                "status": "succeeded",
                "evidence_count": 1,
                "error_code": None,
            }
        }
        manifest["steps"] = [
            {
                "capability": "document.text.extract",
                "provider": "text-read",
                "status": "succeeded",
                "reason": None,
            }
        ]
        text_ready = True

    # ── Build evidence fragment skeleton ──
    fragment = {
        "schema_version": "oks-evidence-fragment/v0.1",
        "fragment_id": fragment_id,
        "source_id": source_id,
        "producer": {
            "runtime": "oks",
            "provider": "text-read" if is_text else "ok-ingest-prepare",
            "tool": "agent-runtime" if is_text else "ingest-prepare",
        },
        "status": "succeeded" if is_text else "pending",
        "artifacts": [
            {
                "artifact_id": artifact_id,
                "kind": "primary_text",
                "path": artifact_path,
                "sha256": content_hash,
            }
        ],
        "evidence": manifest["evidence_records"],
        "modalities": manifest["modalities"],
        "agent_notes": "Pre-filled by oks ingest prepare" if is_text else None,
    }

    # ── Write files ──
    _write_json(manifest_dir / "source-envelope.json", envelope)
    _write_json(manifest_dir / "evidence-manifest.json", manifest)
    _write_json(fragments_dir / f"{fragment_id}.json", fragment)

    files_generated = [
        "source-envelope.json",
        "evidence-manifest.json",
        f"fragments/{fragment_id}.json",
    ]
    if is_text and source_bytes:
        files_generated.append(f"artifacts/{artifact_path}")

    next_step = _next_step(text_ready, run_id)

    return {
        "run_id": run_id,
        "workspace": str(runs_dir),
        "manifest_dir": str(manifest_dir),
        "source": source,
        "modality": modality,
        "access_mode": access_mode,
        "source_id": source_id,
        "content_hash": content_hash,
        "files_generated": files_generated,
        "text_ready": text_ready,
        "next_step": next_step,
    }


# ── helpers ─────────────────────────────────────────────────────────


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Atomic JSON write."""
    import tempfile

    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with _os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            _os.fsync(f.fileno())
        _os.replace(tmp, str(path))
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def _title_from_source(source: str) -> str:
    """Derive a human-readable title from a file path or URL."""
    path = Path(source.split("?", 1)[0])
    if path.suffix:
        return path.stem.replace("-", " ").replace("_", " ")
    if source.startswith(("http://", "https://")):
        return "Web Content"
    return "Untitled Source"


def _media_type(source: str) -> str | None:
    """Map file extension to media type."""
    suffix = Path(source.split("?", 1)[0]).suffix.lower()
    known = {
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".json": "application/json",
        ".yaml": "text/yaml",
        ".yml": "text/yaml",
        ".html": "text/html",
        ".htm": "text/html",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    return known.get(suffix)


def _next_step(text_ready: bool, run_id: str) -> str:
    if text_ready:
        return (
            "Protocol skeleton is complete.  Evidence is pre-filled for this text source. "
            f"Run: oks raw-commit .oks/runs/{run_id}/manifest/ "
            "Then generate Candidate and proceed to /promote."
        )
    return (
        "Protocol skeleton created.  Fill evidence_records in evidence-manifest.json "
        "and add evidence content to artifacts/.  Then run: "
        f"oks raw-commit .oks/runs/{run_id}/manifest/"
    )
