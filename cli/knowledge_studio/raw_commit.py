"""``oks raw commit`` — validate and persist an Agent-submitted evidence bundle.

Protocol: the Agent submits a directory containing:

    <manifest-dir>/
    ├── source-envelope.json
    ├── evidence-manifest.json
    ├── fragments/                  # optional fragment snapshots
    └── artifacts/                  # all evidence files

``oks raw commit`` validates structural integrity, cross-references,
artifact existence + hash matching, and locator legality.  On success
it assembles a Raw Bundle v0.2 and atomically writes it to ``raw/``.

This module does NOT call AI APIs, select extractors, or judge content
quality (CONSTITUTION P4, P5).
"""

from __future__ import annotations

import json
import os as _os
import re
import shutil
import tempfile as _tempfile
import uuid
from datetime import datetime, timezone
from hashlib import sha256 as _sha256
from pathlib import Path
from typing import Any

from knowledge_studio.store import repo_root


def create_run_workspace(source: str) -> dict[str, Any]:
    """Create an isolated Run Workspace for a source without invoking any Agent.

    Returns ``{run_id, workspace, source}`` ready for handoff to an Agent host.
    This function does NOT call any AI API or select any provider.
    """
    run_id = f"run:{uuid.uuid4().hex[:12]}"
    knowledge_root = Path(_os.environ.get("OKS_ROOT", repo_root()))
    runs_dir = knowledge_root / ".oks" / "runs" / run_id
    workspace_dir = runs_dir / "work"
    try:
        workspace_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass  # best effort

    return {
        "run_id": run_id,
        "workspace": str(workspace_dir),
        "source": source,
        "instruction": (
            "Open this workspace with a supported Agent Host (Claude Code, Codex) "
            "and run the /ingest skill."
        ),
    }

# ── Locator validation table (module-level, used by _check_locators) ─

VALID_LOCATOR_KINDS_BY_REQUIRED: dict[str, tuple[str, ...]] = {
    "page": ("page",),
    "bbox": ("bbox",),
    "timestamp": ("start_ms", "end_ms"),
    "dom": ("xpath_fragment",),
    "document": (),
    "custom": ("custom_label",),
}


# ── Error codes ───────────────────────────────────────────────────

class CommitError(Exception):
    """Structured rejection from oks raw commit."""
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


# ── Validation helpers ────────────────────────────────────────────

def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CommitError("FILE_NOT_FOUND", str(exc)) from exc
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CommitError("INVALID_JSON", f"{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CommitError("INVALID_JSON", f"{path}: must be a JSON object")
    return value


def _validate_envelope(envelope: dict[str, Any]) -> None:
    sv = envelope.get("schema_version")
    if sv != "oks-source-envelope/v0.1":
        raise CommitError("UNSUPPORTED_SCHEMA_VERSION",
                          f"source-envelope.json schema_version must be "
                          f"'oks-source-envelope/v0.1', got {sv!r}")

    required = ["source_id", "source_uri", "source_modality", "access_mode",
                "captured_at", "captured_by", "content_hash", "evidence_manifest_ref"]
    for field in required:
        if not envelope.get(field):
            raise CommitError("INVALID_ENVELOPE",
                              f"source-envelope.json: missing or empty field {field!r}",
                              {"field": field})

    cb = envelope["captured_by"]
    if not isinstance(cb, dict) or not cb.get("runtime"):
        raise CommitError("INVALID_ENVELOPE",
                          "source-envelope.json: captured_by.runtime must not be empty")

    ch = envelope["content_hash"]
    if not re.fullmatch(r"[a-f0-9]{64}", str(ch)):
        raise CommitError("INVALID_ENVELOPE",
                          "source-envelope.json: content_hash must be 64 hex chars")


def _validate_manifest(manifest: dict[str, Any]) -> None:
    sv = manifest.get("schema_version")
    if sv != "oks-evidence-manifest/v0.1":
        raise CommitError("UNSUPPORTED_SCHEMA_VERSION",
                          f"evidence-manifest.json schema_version must be "
                          f"'oks-evidence-manifest/v0.1', got {sv!r}")

    required = ["manifest_id", "source_id", "status", "fragment_refs",
                "primary_artifact", "evidence_records", "modalities", "provenance"]
    for field in required:
        val = manifest.get(field)
        if val is None or (isinstance(val, (str, list, tuple)) and not val):
            raise CommitError("INVALID_MANIFEST",
                              f"evidence-manifest.json: missing or empty field {field!r}",
                              {"field": field})

    status = manifest["status"]
    if status not in ("complete", "partial"):
        raise CommitError("INVALID_MANIFEST",
                          f"manifest status must be 'complete' or 'partial', got {status!r}")

    if status == "partial":
        if manifest.get("failure_disposition", "none") == "none":
            raise CommitError("INVALID_MANIFEST",
                              "partial manifest must declare a failure_disposition")
        if not manifest.get("warnings"):
            raise CommitError("INVALID_MANIFEST",
                              "partial manifest must have at least one warning")


def _cross_check(envelope: dict[str, Any], manifest: dict[str, Any]) -> None:
    if envelope["source_id"] != manifest["source_id"]:
        raise CommitError("MANIFEST_SOURCE_MISMATCH",
                          f"source-envelope.source_id ({envelope['source_id']!r}) != "
                          f"evidence-manifest.source_id ({manifest['source_id']!r})",
                          {"envelope_source_id": envelope["source_id"],
                           "manifest_source_id": manifest["source_id"]})


def _check_artifacts(manifest: dict[str, Any], artifacts_dir: Path) -> None:
    all_arts = [manifest["primary_artifact"]] + manifest.get("supplementary_artifacts", [])
    artifact_ids: set[str] = set()

    for art in all_arts:
        aid = art.get("artifact_id", "")
        path_str = art.get("path", "")
        declared_hash = art.get("sha256", "")

        if not aid or not path_str or not declared_hash:
            raise CommitError("INVALID_ARTIFACT",
                              f"artifact missing required fields: {art}")

        if aid in artifact_ids:
            raise CommitError("DUPLICATE_ARTIFACT_ID",
                              f"duplicate artifact_id: {aid!r}")
        artifact_ids.add(aid)

        fp = artifacts_dir / path_str
        if not fp.is_file():
            raise CommitError("MISSING_ARTIFACT",
                              f"artifact file not found: {path_str}",
                              {"artifact_id": aid, "path": path_str})

        actual = _sha256(fp.read_bytes()).hexdigest()
        if actual != declared_hash:
            raise CommitError("ARTIFACT_HASH_MISMATCH",
                              f"hash mismatch for {aid!r}: "
                              f"declared {declared_hash[:16]}..., actual {actual[:16]}...",
                              {"artifact_id": aid,
                               "expected": declared_hash,
                               "actual": actual})


def _check_evidence_cross_ref(manifest: dict[str, Any]) -> None:
    all_arts = [manifest["primary_artifact"]] + manifest.get("supplementary_artifacts", [])
    aid_set = {a["artifact_id"] for a in all_arts}

    for rec in manifest["evidence_records"]:
        rec_aid = rec.get("artifact_id", "")
        if rec_aid not in aid_set:
            raise CommitError("ORPHAN_EVIDENCE",
                              f"evidence record {rec.get('evidence_id', '?')!r} "
                              f"references unknown artifact_id {rec_aid!r}",
                              {"evidence_id": rec.get("evidence_id"),
                               "artifact_id": rec_aid})

    # Modality count consistency
    declared = sum(m.get("evidence_count", 0) for m in manifest["modalities"].values())
    actual = len(manifest["evidence_records"])
    if declared != actual:
        raise CommitError("EVIDENCE_COUNT_MISMATCH",
                          f"modality evidence_count total ({declared}) != "
                          f"actual evidence records ({actual})")


def _check_locators(manifest: dict[str, Any]) -> list[str]:
    """Validate each evidence locator; return warnings for legacy locators."""
    warnings: list[str] = []
    for rec in manifest["evidence_records"]:
        loc = rec.get("locator", {})
        if not isinstance(loc, dict) or not loc:
            raise CommitError("INVALID_LOCATOR",
                              f"evidence {rec.get('evidence_id', '?')!r}: "
                              f"locator must be a non-empty object")

        kind = loc.get("kind")
        if kind is None:
            warnings.append(
                f"evidence {rec.get('evidence_id', '?')!r}: "
                f"legacy locator without 'kind' field"
            )
        elif kind not in VALID_LOCATOR_KINDS_BY_REQUIRED:
            raise CommitError("UNKNOWN_LOCATOR_KIND",
                              f"locator kind {kind!r} not recognized",
                              {"kind": kind})
        else:
            for req_field in VALID_LOCATOR_KINDS_BY_REQUIRED[kind]:
                if req_field not in loc:
                    raise CommitError("INCOMPLETE_LOCATOR",
                                      f"locator kind {kind!r} requires field {req_field!r}",
                                      {"kind": kind, "missing": req_field})
    return warnings


# ── Assembly ──────────────────────────────────────────────────────

def _assemble_bundle(
    envelope: dict[str, Any],
    manifest: dict[str, Any],
    manifest_dir: Path,
    output: Path,
) -> Path:
    """Copy artifacts and write Raw Bundle v0.2 files atomically.

    Uses the existing ``_shared.atomic_write`` pattern via manual
    mkstemp+fsync+os.replace for core bundle files.  The v0.2 schema
    remains unchanged — we add source-envelope.json and
    evidence-manifest.json as supplementary provenance files alongside
    the existing content.md / evidence.jsonl / bundle.json.
    """
    artifacts_dir = manifest_dir / "artifacts"
    fragments_dir = manifest_dir / "fragments"

    output = output.expanduser().resolve()
    if output.exists():
        raise CommitError("BUNDLE_ALREADY_EXISTS",
                          f"output directory already exists: {output}. "
                          f"Use --overwrite to replace.")

    output.mkdir(parents=True)
    (output / "assets").mkdir()
    (output / "source").mkdir()
    (output / "derived").mkdir()
    (output / "derived" / "fragments").mkdir()

    # ── Atomic write helper ──
    def _atomic_write(path: Path, payload: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, tmp = _tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with _os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                _os.fsync(stream.fileno())
            _os.replace(tmp, str(path))
            try:
                fd = _os.open(str(path.parent), _os.O_RDONLY)
                _os.fsync(fd)
                _os.close(fd)
            except OSError:
                pass
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    # ── Copy primary artifact as content.md ──
    primary = manifest["primary_artifact"]
    primary_src = artifacts_dir / primary["path"]
    media_type = primary.get("media_type", "")
    if media_type.startswith("text/") or media_type in ("application/json",):
        content_text = primary_src.read_text(encoding="utf-8")
        _atomic_write(output / "content.md", content_text.rstrip() + "\n")
    else:
        # Binary artifact (PDF, image, etc.) — copy as-is and write a stub content.md
        _atomic_write(output / "content.md",
                      f"Binary artifact: {primary['path']} ({media_type}, {primary.get('byte_size', 0)} bytes)\n"
                      f"See derived/{primary['path']} for the original file.\n")
        derived_dir = output / "derived"
        derived_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(primary_src, derived_dir / primary["path"])

    # ── Write evidence.jsonl ──
    evidence_lines = []
    for rec in manifest["evidence_records"]:
        evidence_lines.append(json.dumps(rec, ensure_ascii=False) + "\n")
    _atomic_write(output / "evidence.jsonl", "".join(evidence_lines))

    # ── Copy supplementary artifacts ──
    all_arts = [manifest["primary_artifact"]] + manifest.get("supplementary_artifacts", [])
    for art in all_arts:
        src = artifacts_dir / art["path"]
        if art is primary:
            continue  # already written as content.md
        # Put in derived/ if it's a supplementary artifact
        dest = output / "derived" / art["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    # ── Copy fragment snapshots ──
    if fragments_dir.is_dir():
        for fp in fragments_dir.iterdir():
            if fp.is_file():
                shutil.copy2(fp, output / "derived" / "fragments" / fp.name)

    # ── Generate stable ids ──
    source_hash = envelope["content_hash"]
    capture_id = envelope.get("source_id", f"cap-{source_hash[:16]}")
    bundle_id = f"bundle:{source_hash[:16]}"
    generated_at = datetime.now(timezone.utc).isoformat()

    # ── Write metadata.json ──
    metadata = {
        "schema_version": "raw-multimodal/v0.1",
        "capture_id": capture_id,
        "source": {
            "url": envelope.get("source_uri"),
            "title": envelope.get("title"),
            "author": None,
            "collected_at": generated_at,
        },
        "source_type": "local",
        "modalities": list(manifest.get("modalities", {}).keys()),
        "route": ["agent.ingest"],
        "extractors": [
            {"name": "agent", "version": "oks-agent-native/v0.1"},
        ],
        "processing_status": manifest["status"],
        "review_status": "pending",
        "benchmark": False,
        "human_context": "required",
        "execution_protocol": manifest["schema_version"],
        "provider": "agent",
        "capability": "agent.ingest",
        "failure_disposition": manifest.get("failure_disposition", "none"),
    }
    _atomic_write(output / "metadata.json",
                   json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")

    # ── Write quality-report.json ──
    coverage: dict[str, dict[str, Any]] = {}
    for name, mod in manifest.get("modalities", {}).items():
        ec = mod.get("evidence_count", 0)
        coverage[name] = {
            "expected": 1,
            "observed": 1 if ec > 0 else 0,
            "status": "passed" if ec > 0 else "partial",
        }
    quality = {
        "schema_version": "raw-multimodal/v0.1",
        "processing_status": manifest["status"],
        "review_status": "pending",
        "evidence_count": len(manifest["evidence_records"]),
        "asset_count": max(0, len(all_arts) - 1),
        "coverage_status": manifest["status"],
        "coverage_checks": coverage,
        "warnings": list(manifest.get("warnings", [])),
        "errors": [],
        "human_fallback": (
            "Agent-native ingest.  Review the evidence manifest before "
            "creating a Candidate."
        ),
    }
    _atomic_write(output / "quality-report.json",
                   json.dumps(quality, ensure_ascii=False, indent=2) + "\n")

    # ── Write source-envelope.json and evidence-manifest.json snapshots ──
    _atomic_write(output / "source-envelope.json",
                   json.dumps(envelope, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(output / "evidence-manifest.json",
                   json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    # ── Write raw.md (entry point) ──
    warnings_text = "\n".join(
        f"- {w}" for w in manifest.get("warnings", [])
    ) or "- 无\n"
    raw_md = (
        f"---\nschema_version: raw-multimodal/v0.1\n"
        f"capture_id: {capture_id}\n"
        f"processing_status: {manifest['status']}\n"
        f"review_status: pending\n"
        f"execution_protocol: {manifest['schema_version']}\n"
        f"---\n\n"
        f"# {envelope.get('title') or 'Agent-captured source'}\n\n"
        f"## 来源\n\n- URI：`{envelope.get('source_uri', '')}`\n"
        f"- Agent：`{envelope.get('captured_by', {}).get('runtime', '?')}`\n\n"
        f"## Raw 提取物\n\n- [正文](content.md)\n"
        f"- [原子证据](evidence.jsonl)：{len(manifest['evidence_records'])} 条\n"
        f"- [Source Envelope](source-envelope.json)\n"
        f"- [Evidence Manifest](evidence-manifest.json)\n\n"
        f"## 已知限制\n\n{warnings_text}"
    )
    _atomic_write(output / "raw.md", raw_md)

    # ── Generate processing-runs.jsonl ──
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    run_entry = {
        "run_id": run_id,
        "capture_id": capture_id,
        "status": manifest["status"],
        "recipe_version": "oks-agent-native-ingest/v0.1",
        "started_at": envelope.get("captured_at", generated_at),
        "finished_at": generated_at,
    }
    _atomic_write(output / "processing-runs.jsonl",
                   json.dumps(run_entry, ensure_ascii=False) + "\n")

    return output


# ── Main entry point ──────────────────────────────────────────────

def raw_commit(
    manifest_dir: str | Path,
    *,
    output: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Validate and commit an Agent-submitted evidence bundle.

    Args:
        manifest_dir: Path to the directory containing
            source-envelope.json, evidence-manifest.json, and artifacts/.
        output: Target directory for the Raw Bundle.  If None, a
            date-based path under ``raw/`` is generated.
        overwrite: If True, replace an existing bundle directory.

    Returns:
        ``{status: "committed", bundle_id, bundle_path, source_id, ...}``

    Raises:
        CommitError: On any structural or integrity violation.
    """
    md = Path(manifest_dir).expanduser().resolve()
    if not md.is_dir():
        raise CommitError("MANIFEST_DIR_NOT_FOUND",
                          f"manifest directory does not exist: {md}")

    envelope_path = md / "source-envelope.json"
    manifest_path = md / "evidence-manifest.json"
    artifacts_dir = md / "artifacts"

    # ── Step 1-2: Read + validate ──
    envelope = _read_json(envelope_path)
    _validate_envelope(envelope)

    manifest = _read_json(manifest_path)
    _validate_manifest(manifest)

    # ── Step 3: Cross-reference ──
    _cross_check(envelope, manifest)

    # ── Step 4: Fragment refs existence ──
    fragments_dir = md / "fragments"
    for fid in manifest.get("fragment_refs", []):
        # Fragment refs are identifiers, not files — we just check they're non-empty
        pass  # validated in _validate_manifest

    # ── Step 5: Artifact existence + hash ──
    if not artifacts_dir.is_dir():
        raise CommitError("MISSING_ARTIFACTS_DIR",
                          f"artifacts/ directory not found: {artifacts_dir}")
    _check_artifacts(manifest, artifacts_dir)

    # ── Step 6-7: Evidence cross-ref + locator ──
    _check_evidence_cross_ref(manifest)
    locator_warnings = _check_locators(manifest)

    # ── Step 8: Determine output path ──
    if output is None:
        root = repo_root()
        today = datetime.now(timezone.utc)
        date_part = today.strftime("%Y/%m/%d")
        source_hash = envelope["content_hash"]
        output = (
            Path(root) / "raw" / date_part / "agent-capture"
            / f"bundle-{source_hash[:16]}"
        )
    else:
        output = Path(output).expanduser().resolve()

    if output.exists() and not overwrite:
        raise CommitError("BUNDLE_ALREADY_EXISTS",
                          f"output directory already exists: {output}. "
                          f"Use --overwrite to replace.")

    if output.exists() and overwrite:
        shutil.rmtree(output)

    # ── Step 9: Assemble ──
    bundle_path = _assemble_bundle(envelope, manifest, md, output)

    return {
        "status": "committed",
        "bundle_id": f"bundle:{envelope['content_hash'][:16]}",
        "bundle_path": str(bundle_path),
        "source_id": envelope["source_id"],
        "content_hash": envelope["content_hash"],
        "evidence_count": len(manifest.get("evidence_records", [])),
        "artifact_count": 1 + len(manifest.get("supplementary_artifacts", [])),
        "locator_warnings": locator_warnings,
    }
