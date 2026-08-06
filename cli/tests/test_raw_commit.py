"""Formal pytest for Gate RC-PROTOCOL-01 — Raw Bundle v0.2 strict schema compliance.

Covers:
    - derived field: [] when no supplementary, proper entries when present
    - Supplementary artifact semantics (derived/ vs source/)
    - All declared paths exist on disk
    - Bundle JSON validation against formal raw-bundle-v0.2 schema
    - Locator positive (6 kinds) and negative (6 cases) validation
    - Artifact kind -> derived kind mapping (8 mappings)
    - Legacy locator rejection (no longer silently accepted)

These tests call ``oks raw-commit`` as a subprocess so they exercise the
exact same code path a real Agent would hit.
"""

import json
import hashlib
import subprocess
import tempfile
from pathlib import Path

import pytest


# ── helpers ──────────────────────────────────────────────────────────

def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_manifest(
    art_dir: Path,
    primary_name: str,
    primary_content: str,
    evidence_records: list[dict],
    supp: tuple[tuple[str, str, str], ...] = (),
) -> tuple[Path, str]:
    """Build a minimal Agent-submitted manifest directory.

    Returns ``(manifest_dir, primary_hash)``.
    """
    m = art_dir.parent
    p = art_dir / primary_name
    p.write_text(primary_content, encoding="utf-8")
    ph = _sha_file(p)

    supp_list: list[dict] = []
    for sname, scontent, skind in supp:
        sp = art_dir / sname
        sp.write_text(scontent, encoding="utf-8")
        sh = _sha_file(sp)
        supp_list.append(
            {"artifact_id": sname, "kind": skind, "path": sname, "sha256": sh}
        )

    sid = f"src-{ph[:8]}"
    (m / "source-envelope.json").write_text(
        json.dumps(
            {
                "schema_version": "oks-source-envelope/v0.1",
                "source_id": sid,
                "source_uri": "file:///x",
                "source_modality": "text",
                "access_mode": "local_file",
                "captured_at": "2026-08-06T12:00:00Z",
                "captured_by": {"runtime": "claude-code"},
                "content_hash": ph,
                "evidence_manifest_ref": "m",
            }
        )
    )
    (m / "evidence-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "oks-evidence-manifest/v0.1",
                "manifest_id": "m",
                "source_id": sid,
                "status": "complete",
                "fragment_refs": ["f1"],
                "primary_artifact": {
                    "artifact_id": primary_name,
                    "kind": "primary_text",
                    "path": primary_name,
                    "sha256": ph,
                },
                "supplementary_artifacts": supp_list,
                "evidence_records": evidence_records,
                "modalities": {
                    "text": {
                        "modality": "text",
                        "status": "succeeded",
                        "evidence_count": len(evidence_records),
                    }
                },
                "provenance": {"agent": {"runtime": "test"}},
                "failure_disposition": "none",
            }
        )
    )
    return m, ph


def _run_commit(manifest_dir: Path, output: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["oks", "raw-commit", str(manifest_dir), "-o", str(output)],
        capture_output=True,
        text=True,
    )


# ── 1. derived field ─────────────────────────────────────────────────

def test_derived_is_empty_array_without_supplementary():
    """bundle.json ``derived`` is ``[]`` not ``None`` when no supplementary."""
    base = Path(tempfile.mkdtemp(prefix="t1-"))
    art = base / "artifacts"
    art.mkdir()
    m, _ = _make_manifest(
        art,
        "data.txt",
        "content",
        [{"evidence_id": "e1", "artifact_id": "data.txt", "kind": "text",
          "method": "read", "locator": {"kind": "document"}}],
    )
    r = _run_commit(m, base / "out")
    assert r.returncode == 0, f"commit failed: {r.stdout[:200]}"
    bundle = json.loads((base / "out" / "bundle.json").read_text())
    assert isinstance(bundle["derived"], list)
    assert bundle["derived"] == []
    assert len(bundle["sources"]) == 1


def test_derived_has_entries_with_supplementary():
    """bundle.json ``derived`` contains correct entries for supplementary artifacts."""
    base = Path(tempfile.mkdtemp(prefix="t2-"))
    art = base / "artifacts"
    art.mkdir()
    m, _ = _make_manifest(
        art,
        "primary.txt",
        "main",
        [{"evidence_id": "e1", "artifact_id": "primary.txt", "kind": "text",
          "method": "read", "locator": {"kind": "document"}}],
        supp=(("ocr-out.txt", "OCR text", "ocr_result"),),
    )
    r = _run_commit(m, base / "out")
    assert r.returncode == 0, f"commit failed: {r.stdout[:200]}"
    bundle = json.loads((base / "out" / "bundle.json").read_text())
    assert len(bundle["derived"]) == 1
    d = bundle["derived"][0]
    assert d["kind"] == "ocr"
    assert d["path"] == "derived/ocr-out.txt"
    assert "primary.txt" in d["derived_from"]


# ── 2. Supplementary artifact source / derived semantics ─────────────

def test_supplementary_not_in_sources():
    """Supplementary artifacts belong in derived/, not sources/."""
    base = Path(tempfile.mkdtemp(prefix="t3-"))
    art = base / "artifacts"
    art.mkdir()
    m, _ = _make_manifest(
        art,
        "primary.txt",
        "main",
        [{"evidence_id": "e1", "artifact_id": "primary.txt", "kind": "text",
          "method": "read", "locator": {"kind": "document"}}],
        supp=(("screenshot.png", "png-data", "screenshot"),),
    )
    r = _run_commit(m, base / "out")
    assert r.returncode == 0
    bundle = json.loads((base / "out" / "bundle.json").read_text())
    source_entities = [s["entity_id"] for s in bundle["sources"]]
    assert "screenshot.png" not in source_entities, (
        f"Supplementary artifact must not appear in sources[]: {source_entities}"
    )
    assert len(bundle["sources"]) == 1
    assert bundle["sources"][0]["primary_source"] is True


# ── 3. All declared paths exist on disk ──────────────────────────────

def test_all_declared_paths_exist_on_disk():
    """Every path declared in sources[] and derived[] refers to a real file."""
    base = Path(tempfile.mkdtemp(prefix="t4-"))
    art = base / "artifacts"
    art.mkdir()
    m, _ = _make_manifest(
        art,
        "primary.txt",
        "main content",
        [{"evidence_id": "e1", "artifact_id": "primary.txt", "kind": "text",
          "method": "read", "locator": {"kind": "document"}}],
        supp=(("ocr.txt", "ocr", "ocr_result"),),
    )
    r = _run_commit(m, base / "out")
    assert r.returncode == 0
    out = base / "out"
    bundle = json.loads((out / "bundle.json").read_text())
    for s in bundle["sources"]:
        assert (out / s["path"]).is_file(), f"Missing source file: {s['path']}"
    for d in bundle["derived"]:
        assert (out / d["path"]).is_file(), f"Missing derived file: {d['path']}"


# ── 4. Bundle schema validation ──────────────────────────────────────

def test_bundle_json_passes_schema_validation():
    """Assembled bundle.json passes strict jsonschema validation."""
    from jsonschema import validate

    base = Path(tempfile.mkdtemp(prefix="t5-"))
    art = base / "artifacts"
    art.mkdir()
    m, _ = _make_manifest(
        art,
        "data.txt",
        "content",
        [{"evidence_id": "e1", "artifact_id": "data.txt", "kind": "text",
          "method": "read", "locator": {"kind": "document"}}],
        supp=(("screen.png", "img", "screenshot"),),
    )
    r = _run_commit(m, base / "out")
    assert r.returncode == 0
    bundle = json.loads((base / "out" / "bundle.json").read_text())
    from importlib.resources import files as _res_files
    raw_schema = (
        _res_files("knowledge_studio.schemas")
        .joinpath("raw-bundle-v0.2.schema.json")
        .read_text(encoding="utf-8")
    )
    schema = json.loads(raw_schema)
    # This must not raise
    validate(bundle, schema)


# ── 5. Locator positive — all 6 kinds accepted ───────────────────────

@pytest.mark.parametrize("kind,loc", [
    ("page", {"kind": "page", "page": 1}),
    ("bbox", {"kind": "bbox", "bbox": [0, 0, 100, 100]}),
    ("timestamp", {"kind": "timestamp", "start_ms": 0, "end_ms": 1000}),
    ("dom", {"kind": "dom", "xpath_fragment": "//div"}),
    ("document", {"kind": "document"}),
    ("custom", {"kind": "custom", "custom_label": "label"}),
])
def test_locator_valid_kinds_accepted(kind, loc):
    """Every valid locator kind must be accepted by raw-commit."""
    base = Path(tempfile.mkdtemp(prefix=f"t-loc-ok-{kind}-"))
    art = base / "artifacts"
    art.mkdir()
    m, _ = _make_manifest(
        art,
        "t.txt",
        "data",
        [{"evidence_id": f"e-{kind}", "artifact_id": "t.txt", "kind": "text",
          "method": "read", "locator": loc}],
    )
    r = _run_commit(m, base / "out")
    assert r.returncode == 0, f"Locator {loc} was rejected: {r.stdout[:200]}"


# ── 6. Locator negative — 6 failure cases ────────────────────────────

@pytest.mark.parametrize("desc,loc", [
    ("page without page field", {"kind": "page"}),
    ("bbox without bbox field", {"kind": "bbox"}),
    ("timestamp without start_ms", {"kind": "timestamp", "end_ms": 1000}),
    ("dom without xpath_fragment", {"kind": "dom"}),
    ("custom without custom_label", {"kind": "custom"}),
    ("unknown kind", {"kind": "unknown"}),
])
def test_locator_invalid_kinds_rejected(desc, loc):
    """Invalid locators must be rejected with a clear error."""
    base = Path(tempfile.mkdtemp(prefix="t-loc-bad-"))
    art = base / "artifacts"
    art.mkdir()
    m, _ = _make_manifest(
        art,
        "t.txt",
        "data",
        [{"evidence_id": "e-bad", "artifact_id": "t.txt", "kind": "text",
          "method": "read", "locator": loc}],
    )
    r = _run_commit(m, base / "out")
    assert r.returncode != 0, (
        f"Locator '{desc}' should have been rejected but was accepted"
    )


# ── 7. Legacy locator — no longer silently accepted ──────────────────

def test_legacy_locator_without_kind_rejected():
    """Locators without a ``kind`` field are no longer silently accepted."""
    base = Path(tempfile.mkdtemp(prefix="t-legacy-"))
    art = base / "artifacts"
    art.mkdir()
    m, _ = _make_manifest(
        art,
        "x.txt",
        "data",
        [{"evidence_id": "e-legacy", "artifact_id": "x.txt", "kind": "text",
          "method": "read", "locator": {"page": 1}}],
    )
    r = _run_commit(m, base / "out")
    assert r.returncode != 0, (
        "Legacy locator (no 'kind') was silently accepted — should be rejected"
    )
    result = json.loads(r.stdout)
    assert "locator" in str(result).lower() or "kind" in str(result).lower(), (
        f"Error should mention locator/kind: {json.dumps(result)[:200]}"
    )


# ── 8. Artifact kind -> derived kind mapping ─────────────────────────

@pytest.mark.parametrize("art_kind,expected", [
    ("ocr_result", "ocr"),
    ("screenshot", "visual_observation"),
    ("dom_snapshot", "layout"),
    ("rendered_page", "visual_observation"),
    ("api_response", "other"),
    ("page_image", "visual_observation"),
    ("subtitle", "other"),
    ("primary_text", "other"),
])
def test_artifact_kind_maps_to_derived_kind(art_kind, expected):
    """Each artifact ``kind`` maps to the correct derived ``kind``."""
    base = Path(tempfile.mkdtemp(prefix=f"t-map-{art_kind}-"))
    art = base / "artifacts"
    art.mkdir()
    ap = art / "out.dat"
    ap.write_text("derived", encoding="utf-8")
    ah = _sha_file(ap)
    pp = art / "primary.dat"
    pp.write_text("primary", encoding="utf-8")
    ph = _sha_file(pp)

    sid = f"s-{ph[:8]}"
    (base / "source-envelope.json").write_text(
        json.dumps({
            "schema_version": "oks-source-envelope/v0.1", "source_id": sid,
            "source_uri": "file:///x", "source_modality": "text",
            "access_mode": "local_file", "captured_at": "2026-08-06T12:00:00Z",
            "captured_by": {"runtime": "test"}, "content_hash": ph,
            "evidence_manifest_ref": "m",
        })
    )
    (base / "evidence-manifest.json").write_text(
        json.dumps({
            "schema_version": "oks-evidence-manifest/v0.1", "manifest_id": "m",
            "source_id": sid, "status": "complete", "fragment_refs": ["f1"],
            "primary_artifact": {"artifact_id": "primary.dat", "kind": "primary_text",
                                 "path": "primary.dat", "sha256": ph},
            "supplementary_artifacts": [{"artifact_id": "out.dat", "kind": art_kind,
                                         "path": "out.dat", "sha256": ah}],
            "evidence_records": [{"evidence_id": "e1", "artifact_id": "primary.dat",
                "kind": "text", "method": "read", "locator": {"kind": "document"}}],
            "modalities": {"text": {"modality": "text", "status": "succeeded",
                                    "evidence_count": 1}},
            "provenance": {"agent": {"runtime": "test"}},
            "failure_disposition": "none",
        })
    )
    r = _run_commit(base, base / "out")
    assert r.returncode == 0, f"Commit failed: {r.stdout[:200]}"
    bundle = json.loads((base / "out" / "bundle.json").read_text())
    assert len(bundle["derived"]) == 1
    actual = bundle["derived"][0]["kind"]
    assert actual == expected, (
        f"Artifact kind '{art_kind}' mapped to derived '{actual}', expected '{expected}'"
    )
