"""``oks raw commit`` — validate and persist an Agent-submitted evidence bundle.

Protocol: the Agent submits a directory containing:

    <manifest-dir>/
    ├── source-envelope.json
    ├── evidence-manifest.json
    ├── fragments/                  # optional fragment snapshots
    └── artifacts/                  # all evidence files

``oks raw commit`` validates against the formal JSON Schemas in
``schemas/``, checks cross-references, artifact existence + hash
matching, and locator legality.  On success it assembles a Raw Bundle
v0.2 and atomically writes it to ``raw/``.

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
from importlib.resources import files
from pathlib import Path
from typing import Any

from knowledge_studio.store import repo_root


def create_run_workspace(source: str) -> dict[str, Any]:
    """Create an isolated Run Workspace for a source without invoking any Agent.

    Returns ``{run_id, workspace, source}`` ready for handoff to an Agent host.
    This function does NOT call any AI API or select any provider.
    """
    run_id = f"run-{uuid.uuid4().hex[:12]}"
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


# ── Schema loading (cached) ───────────────────────────────────────

_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}

def _load_schema(name: str) -> dict[str, Any]:
    """Load a JSON Schema from the packaged schemas directory."""
    if name not in _SCHEMA_CACHE:
        schema_text = (
            files("knowledge_studio.schemas").joinpath(name).read_text(encoding="utf-8")
        )
        _SCHEMA_CACHE[name] = json.loads(schema_text)
    return _SCHEMA_CACHE[name]


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
    """Validate source-envelope.json against the formal JSON Schema."""
    try:
        from jsonschema import validate, ValidationError as JsValidationError
    except ImportError:
        # Graceful degradation: skip schema validation if jsonschema not installed
        # (structural checks below are kept as safety net)
        pass
    else:
        schema = _load_schema("source-envelope-v0.1.schema.json")
        try:
            validate(envelope, schema)
        except JsValidationError as exc:
            raise CommitError(
                "INVALID_ENVELOPE",
                f"source-envelope.json: {exc.message}",
                {"json_path": exc.json_path, "schema_path": list(exc.relative_schema_path)},
            ) from exc

    # Semantic checks beyond what JSON Schema can express
    ch = envelope.get("content_hash", "")
    if not re.fullmatch(r"[a-f0-9]{64}", str(ch)):
        raise CommitError(
            "INVALID_ENVELOPE",
            "source-envelope.json: content_hash must be 64 hex chars",
        )


def _validate_manifest(manifest: dict[str, Any]) -> None:
    """Validate evidence-manifest.json against the formal JSON Schema."""
    try:
        from jsonschema import validate, ValidationError as JsValidationError
    except ImportError:
        pass
    else:
        schema = _load_schema("evidence-manifest-v0.1.schema.json")
        try:
            validate(manifest, schema)
        except JsValidationError as exc:
            raise CommitError(
                "INVALID_MANIFEST",
                f"evidence-manifest.json: {exc.message}",
                {"json_path": exc.json_path, "schema_path": list(exc.relative_schema_path)},
            ) from exc

    # Semantic check: partial must not use 'none' disposition
    if manifest.get("status") == "partial":
        fd = manifest.get("failure_disposition", "none")
        if fd == "none":
            raise CommitError(
                "INVALID_MANIFEST",
                "partial manifest must declare a non-'none' failure_disposition",
            )


def _cross_check(envelope: dict[str, Any], manifest: dict[str, Any]) -> None:
    if envelope["source_id"] != manifest["source_id"]:
        raise CommitError(
            "MANIFEST_SOURCE_MISMATCH",
            f"source-envelope.source_id ({envelope['source_id']!r}) != "
            f"evidence-manifest.source_id ({manifest['source_id']!r})",
            {
                "envelope_source_id": envelope["source_id"],
                "manifest_source_id": manifest["source_id"],
            },
        )


def _check_artifacts(manifest: dict[str, Any], artifacts_dir: Path) -> None:
    all_arts = [manifest["primary_artifact"]] + manifest.get("supplementary_artifacts", [])
    artifact_ids: set[str] = set()

    for art in all_arts:
        aid = art.get("artifact_id", "")
        path_str = art.get("path", "")
        declared_hash = art.get("sha256", "")

        if not aid or not path_str or not declared_hash:
            raise CommitError(
                "INVALID_ARTIFACT",
                f"artifact missing required fields: {art}",
            )

        if aid in artifact_ids:
            raise CommitError("DUPLICATE_ARTIFACT_ID", f"duplicate artifact_id: {aid!r}")
        artifact_ids.add(aid)

        fp = artifacts_dir / path_str
        # Prevent directory traversal
        try:
            fp.resolve().relative_to(artifacts_dir.resolve())
        except ValueError:
            raise CommitError(
                "PATH_TRAVERSAL",
                f"artifact path escapes artifacts/: {path_str}",
                {"artifact_id": aid, "path": path_str},
            )

        if not fp.is_file():
            raise CommitError(
                "MISSING_ARTIFACT",
                f"artifact file not found: {path_str}",
                {"artifact_id": aid, "path": path_str},
            )

        actual = _sha256(fp.read_bytes()).hexdigest()
        if actual != declared_hash:
            raise CommitError(
                "ARTIFACT_HASH_MISMATCH",
                f"hash mismatch for {aid!r}: "
                f"declared {declared_hash[:16]}..., actual {actual[:16]}...",
                {"artifact_id": aid, "expected": declared_hash, "actual": actual},
            )


def _check_evidence_cross_ref(manifest: dict[str, Any]) -> None:
    all_arts = [manifest["primary_artifact"]] + manifest.get("supplementary_artifacts", [])
    aid_set = {a["artifact_id"] for a in all_arts}

    for rec in manifest["evidence_records"]:
        rec_aid = rec.get("artifact_id", "")
        if rec_aid not in aid_set:
            raise CommitError(
                "ORPHAN_EVIDENCE",
                f"evidence record {rec.get('evidence_id', '?')!r} "
                f"references unknown artifact_id {rec_aid!r}",
                {"evidence_id": rec.get("evidence_id"), "artifact_id": rec_aid},
            )

    # Modality count consistency
    declared = sum(
        m.get("evidence_count", 0) for m in manifest["modalities"].values()
    )
    actual = len(manifest["evidence_records"])
    if declared != actual:
        raise CommitError(
            "EVIDENCE_COUNT_MISMATCH",
            f"modality evidence_count total ({declared}) != "
            f"actual evidence records ({actual})",
        )


def _check_locators(manifest: dict[str, Any]) -> list[str]:
    """Validate each evidence locator; return warnings for legacy locators."""
    warnings: list[str] = []
    for rec in manifest["evidence_records"]:
        loc = rec.get("locator", {})
        if not isinstance(loc, dict) or not loc:
            raise CommitError(
                "INVALID_LOCATOR",
                f"evidence {rec.get('evidence_id', '?')!r}: "
                f"locator must be a non-empty object",
            )

        kind = loc.get("kind")
        if kind is None:
            warnings.append(
                f"evidence {rec.get('evidence_id', '?')!r}: "
                f"legacy locator without 'kind' field"
            )
        elif kind not in VALID_LOCATOR_KINDS_BY_REQUIRED:
            raise CommitError(
                "UNKNOWN_LOCATOR_KIND",
                f"locator kind {kind!r} not recognized",
                {"kind": kind},
            )
        else:
            for req_field in VALID_LOCATOR_KINDS_BY_REQUIRED[kind]:
                if req_field not in loc:
                    raise CommitError(
                        "INCOMPLETE_LOCATOR",
                        f"locator kind {kind!r} requires field {req_field!r}",
                        {"kind": kind, "missing": req_field},
                    )
    return warnings


# ── Assembly ──────────────────────────────────────────────────────

def _assemble_bundle(
    envelope: dict[str, Any],
    manifest: dict[str, Any],
    manifest_dir: Path,
    output: Path,
) -> Path:
    """Assemble a Raw Bundle v0.2 on disk.

    Writes:
      - bundle.json  (v0.2 bundle manifest)
      - content.md
      - evidence.jsonl
      - quality-report.json
      - processing-runs.jsonl
      - source-envelope.json (snapshot)
      - evidence-manifest.json (snapshot)
      - raw.md (entry point)
      - source/   (original files)
      - assets/   (empty, reserved)
      - derived/  (fragments, supplementary artifacts)
    """
    artifacts_dir = manifest_dir / "artifacts"
    fragments_dir = manifest_dir / "fragments"

    output = output.expanduser().resolve()

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

    output.mkdir(parents=True)
    (output / "source").mkdir()
    (output / "assets").mkdir()
    (output / "derived").mkdir()
    (output / "derived" / "fragments").mkdir()

    # ── Generate stable identifiers ──
    source_hash = envelope["content_hash"]
    source_id = envelope["source_id"]
    bundle_id = f"bundle:{source_hash[:16]}"
    generated_at = datetime.now(timezone.utc).isoformat()
    # Preserve the Agent's run_id from the manifest directory path
    run_id = manifest_dir.parent.name if manifest_dir.parent.name.startswith("run-") else f"run-{uuid.uuid4().hex[:12]}"

    primary = manifest["primary_artifact"]
    primary_src = artifacts_dir / primary["path"]

    # ── Copy primary source file to source/ ──
    source_dest = output / "source" / primary["path"]
    source_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(primary_src, source_dest)

    # ── content.md — text rendering ──
    media_type = primary.get("media_type", "")
    if media_type.startswith("text/") or media_type in ("application/json",):
        content_text = primary_src.read_text(encoding="utf-8")
        _atomic_write(output / "content.md", content_text.rstrip() + "\n")
    else:
        _atomic_write(
            output / "content.md",
            f"Binary artifact: {primary['path']} ({media_type}, {primary.get('byte_size', 0)} bytes)\n"
            f"See source/{primary['path']} for the original file.\n",
        )

    # ── evidence.jsonl ──
    evidence_lines = []
    for rec in manifest["evidence_records"]:
        evidence_lines.append(json.dumps(rec, ensure_ascii=False) + "\n")
    _atomic_write(output / "evidence.jsonl", "".join(evidence_lines))

    # ── Supplementary artifacts → derived/ ──
    all_arts = [manifest["primary_artifact"]] + manifest.get("supplementary_artifacts", [])
    for art in all_arts:
        src = artifacts_dir / art["path"]
        if art is primary:
            continue
        dest = output / "derived" / art["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    # ── Fragment snapshots → derived/fragments/ ──
    if fragments_dir.is_dir():
        for fp in fragments_dir.iterdir():
            if fp.is_file():
                shutil.copy2(fp, output / "derived" / "fragments" / fp.name)

    # ── bundle.json (Raw Bundle v0.2 manifest) ──
    sources_list = [
        {
            "entity_id": primary["artifact_id"],
            "path": f"source/{primary['path']}",
            "sha256": primary.get("sha256", source_hash),
            "media_type": media_type or None,
            "snapshot_kind": "content",
            "content_hash_status": "verified",
            "primary_source": True,
        }
    ]
    for art in manifest.get("supplementary_artifacts", []):
        sources_list.append({
            "entity_id": art["artifact_id"],
            "path": f"source/{art['path']}",
            "sha256": art.get("sha256", ""),
            "media_type": art.get("media_type"),
            "snapshot_kind": "content",
            "content_hash_status": "verified",
            "primary_source": False,
        })

    derived_list = []
    derived_entities = []
    for art in manifest.get("supplementary_artifacts", []):
        entity_id = f"derived-{art['artifact_id']}"
        derived_list.append({
            "entity_id": entity_id,
            "kind": "other",
            "path": f"derived/{art['path']}",
            "generated_by": "agent-ingest",
            "derived_from": [primary["artifact_id"]],
            "review_status": "not_applicable",
        })
        derived_entities.append(entity_id)

    provenance = {
        "entities": [
            {"id": eid, "type": "file"}
            for eid in [primary["artifact_id"]]
            + [a["artifact_id"] for a in manifest.get("supplementary_artifacts", [])]
            + derived_entities
        ],
        "activities": [
            {
                "id": f"ingest-{run_id}",
                "type": "agent-ingest",
                "started_at": envelope.get("captured_at", generated_at),
                "finished_at": generated_at,
            }
        ],
        "agents": [
            {
                "id": envelope.get("captured_by", {}).get("runtime", "oks-agent"),
                "type": "agent-runtime",
            }
        ],
        "relations": [
            {"type": "wasGeneratedBy", "subject": primary["artifact_id"], "object": f"ingest-{run_id}"},
        ],
    }

    bundle_json = {
        "schema_version": "raw-multimodal/v0.2",
        "bundle_id": bundle_id,
        "capture_id": source_id,
        "content_hash": source_hash,
        "recipe_version": "oks-agent-native-ingest/v0.1",
        "processing_status": manifest["status"],
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
        "sources": sources_list,
        "derived": derived_list if derived_list else None,
        "provenance": provenance,
        "warnings": list(manifest.get("warnings", [])),
    }
    _atomic_write(
        output / "bundle.json",
        json.dumps(bundle_json, ensure_ascii=False, indent=2) + "\n",
    )

    # ── source-envelope.json + evidence-manifest.json snapshots ──
    _atomic_write(
        output / "source-envelope.json",
        json.dumps(envelope, ensure_ascii=False, indent=2) + "\n",
    )
    _atomic_write(
        output / "evidence-manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )

    # ── quality-report.json ──
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
    _atomic_write(
        output / "quality-report.json",
        json.dumps(quality, ensure_ascii=False, indent=2) + "\n",
    )

    # ── raw.md (entry point) ──
    warnings_text = (
        "\n".join(f"- {w}" for w in manifest.get("warnings", [])) or "- 无\n"
    )
    raw_md = (
        f"---\nschema_version: raw-multimodal/v0.2\n"
        f"capture_id: {source_id}\n"
        f"processing_status: {manifest['status']}\n"
        f"review_status: pending\n"
        f"execution_protocol: {manifest['schema_version']}\n"
        f"---\n\n"
        f"# {envelope.get('title') or 'Agent-captured source'}\n\n"
        f"## 来源\n\n- URI：`{envelope.get('source_uri', '')}`\n"
        f"- Agent：`{envelope.get('captured_by', {}).get('runtime', '?')}`\n\n"
        f"## Raw 提取物\n\n- [Bundle Manifest](bundle.json)\n"
        f"- [正文](content.md)\n"
        f"- [原子证据](evidence.jsonl)：{len(manifest['evidence_records'])} 条\n"
        f"- [Source Envelope](source-envelope.json)\n"
        f"- [Evidence Manifest](evidence-manifest.json)\n\n"
        f"## 已知限制\n\n{warnings_text}"
    )
    _atomic_write(output / "raw.md", raw_md)

    # ── processing-runs.jsonl (preserves Agent run_id) ──
    run_entry = {
        "run_id": run_id,
        "capture_id": source_id,
        "status": manifest["status"],
        "recipe_version": "oks-agent-native-ingest/v0.1",
        "started_at": envelope.get("captured_at", generated_at),
        "finished_at": generated_at,
    }
    _atomic_write(
        output / "processing-runs.jsonl",
        json.dumps(run_entry, ensure_ascii=False) + "\n",
    )

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
        raise CommitError(
            "MANIFEST_DIR_NOT_FOUND",
            f"manifest directory does not exist: {md}",
        )

    envelope_path = md / "source-envelope.json"
    manifest_path = md / "evidence-manifest.json"
    artifacts_dir = md / "artifacts"

    # ── Step 1-2: Read + validate against formal JSON Schemas ──
    envelope = _read_json(envelope_path)
    _validate_envelope(envelope)

    manifest = _read_json(manifest_path)
    _validate_manifest(manifest)

    # ── Step 3: Cross-reference ──
    _cross_check(envelope, manifest)

    # ── Step 4: Artifact existence + hash ──
    if not artifacts_dir.is_dir():
        raise CommitError(
            "MISSING_ARTIFACTS_DIR",
            f"artifacts/ directory not found: {artifacts_dir}",
        )
    _check_artifacts(manifest, artifacts_dir)

    # ── Step 5-6: Evidence cross-ref + locator ──
    _check_evidence_cross_ref(manifest)
    locator_warnings = _check_locators(manifest)

    # ── Step 7: Determine output path ──
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
        raise CommitError(
            "BUNDLE_ALREADY_EXISTS",
            f"output directory already exists: {output}. "
            f"Use --overwrite to replace.",
        )

    if output.exists() and overwrite:
        shutil.rmtree(output)

    # ── Step 8: Assemble Raw Bundle v0.2 ──
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
