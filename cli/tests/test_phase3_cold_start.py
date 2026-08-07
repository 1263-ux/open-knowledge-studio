"""Deterministic tests for Phase 3A cold-start product glue.

These tests verify NEW code that the Phase 3A CLI glue introduces:
_provider_status(), _build_capability_summary(), ingest SKILL.md content,
and Claude/Agents skill identity.

They do NOT test Agent behaviour — that belongs in the manual cold-start
walking-skeleton scenario.
"""

from __future__ import annotations

import os
import sys
import tempfile
from importlib.resources import files
from pathlib import Path


# ── _provider_status() ──────────────────────────────────────────────
# Test the REAL production function — no inlined copy.

from knowledge_studio.capability_commands import _provider_status


def test_provider_status_ready():
    """All checks pass → ready."""
    assert _provider_status([], "", "") == "ready"
    assert _provider_status([
        {"type": "command", "name": "python", "available": True},
        {"type": "env_var", "name": "FIRECRAWL_API_KEY", "available": True},
    ], "", "") == "ready"


def test_provider_status_not_configured():
    """Only env var missing, commands available → not_configured."""
    assert _provider_status([
        {"type": "command", "name": "python", "available": True},
        {"type": "env_var", "name": "FIRECRAWL_API_KEY", "available": False},
    ], "", "") == "not_configured"


def test_provider_status_unavailable():
    """Required command missing → unavailable."""
    assert _provider_status([
        {"type": "command", "name": "ffmpeg", "available": False},
    ], "", "") == "unavailable"


def test_provider_status_runtime_only():
    """AgentKey maps to runtime_only regardless of checks."""
    assert _provider_status([], "agentkey", "") == "runtime_only"
    assert _provider_status([
        {"type": "env_var", "name": "AGENTKEY_API_KEY", "available": True},
    ], "agentkey", "") == "runtime_only"


def test_provider_status_blocked():
    """Browser is blocked."""
    assert _provider_status([], "browser", "") == "blocked"


def test_provider_status_experimental():
    """HTTP-fetch, remote-asr, media-ingest are experimental."""
    for pid in ("http-fetch", "remote-asr", "media-ingest"):
        assert _provider_status([], pid, "") == "experimental", f"{pid} should be experimental"


def test_provider_status_optional_failure():
    """Optional command missing with required=False doesn't downgrade to unavailable."""
    assert _provider_status([
        {"type": "command", "name": "optional-tool", "available": False, "required": False},
    ], "", "") == "ready"


# ── _build_capability_summary() ─────────────────────────────────────
# Test the REAL production function — no inlined copy.

from knowledge_studio.capability_commands import _build_capability_summary

_EMPTY_DOCTOR = {"overall": "issues_found", "providers": []}


def test_build_capability_summary_empty():
    """None input returns empty groups."""
    result = _build_capability_summary(None)
    for v in result.values():
        assert v == []


def test_build_capability_summary_filters_always_available():
    """agent-runtime, human, text-read are excluded."""
    doctor = {
        "overall": "healthy",
        "providers": [
            {"id": "agent-runtime", "execution": "agent_native", "status": "ready"},
            {"id": "human", "execution": "human", "status": "ready"},
            {"id": "text-read", "execution": "agent_native", "status": "ready"},
        ],
    }
    result = _build_capability_summary(doctor)
    all_providers = []
    for v in result.values():
        all_providers.extend(v)
    assert all_providers == []


def test_build_capability_summary_groups_local():
    """Local ready providers go to local_ready; local missing to local_missing."""
    doctor = {
        "overall": "issues_found",
        "providers": [
            {"id": "pdf-lite", "execution": "managed", "status": "ready", "label": "PDF-lite"},
            {"id": "rapidocr", "execution": "managed", "status": "unavailable", "label": "RapidOCR"},
        ],
    }
    result = _build_capability_summary(doctor)
    assert len(result["local_ready"]) == 1
    assert result["local_ready"][0]["id"] == "pdf-lite"
    assert len(result["local_missing"]) == 1
    assert result["local_missing"][0]["id"] == "rapidocr"


def test_build_capability_summary_groups_remote():
    """External providers are grouped by status."""
    doctor = {
        "overall": "issues_found",
        "providers": [
            {"id": "firecrawl", "execution": "external", "status": "ready", "label": "Firecrawl"},
            {"id": "some-api", "execution": "external", "status": "not_configured", "label": "SomeAPI"},
            {"id": "agentkey", "execution": "external", "status": "runtime_only", "label": "AgentKey"},
            {"id": "browser", "execution": "external", "status": "blocked", "label": "Browser"},
            {"id": "http-fetch", "execution": "agent_native", "status": "experimental", "label": "HTTP Fetch"},
        ],
    }
    result = _build_capability_summary(doctor)
    assert len(result["remote_ready"]) == 1
    assert result["remote_ready"][0]["id"] == "firecrawl"
    assert len(result["remote_not_configured"]) == 1
    assert result["remote_not_configured"][0]["id"] == "some-api"
    assert len(result["remote_runtime_only"]) == 1
    assert result["remote_runtime_only"][0]["id"] == "agentkey"
    assert len(result["blocked_experimental"]) == 2
    blocked_ids = {p["id"] for p in result["blocked_experimental"]}
    assert blocked_ids == {"browser", "http-fetch"}


# ── Ingest SKILL.md content checks ──────────────────────────────────

_SKILL_REQUIRED_KEYWORDS = [
    "provider_selection",
    "degradation_path",
    "fallback_activated",
    "candidates_considered",
]

_SKILL_MUST_CONSTRAINTS = [
    "MUST write result.json",
    "MUST include `provider_selection`",
    "MUST include `degradation_path`",
    "MUST output the unified result card",
    "MUST record every attempted provider",
]


def _read_skill_text(host: str) -> str:
    """Read the ingest SKILL.md from skill_templates/<host>/skills/ingest/."""
    return (
        files("knowledge_studio.skill_templates")
        .joinpath(host, "skills", "ingest", "SKILL.md")
        .read_text(encoding="utf-8")
    )


def test_ingest_skill_contains_provider_selection_fields():
    """Both Claude and Agents ingest SKILL.md contain provider_selection."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        for keyword in _SKILL_REQUIRED_KEYWORDS:
            assert keyword in text, (
                f"{host}/ingest/SKILL.md missing keyword: {keyword}"
            )


def test_ingest_skill_contains_must_constraints():
    """Both Claude and Agents ingest SKILL.md contain the new MUST constraints."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        for constraint in _SKILL_MUST_CONSTRAINTS:
            assert constraint in text, (
                f"{host}/ingest/SKILL.md missing constraint: {constraint}"
            )


def test_ingest_skill_contains_unified_card():
    """Both versions contain the unified result card output format (Guided UX)."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        assert "摄入完成" in text, f"{host}/ingest/SKILL.md missing unified card header"
        assert "已获得" in text, f"{host}/ingest/SKILL.md missing 已获得"
        assert "缺失" in text, f"{host}/ingest/SKILL.md missing 缺失"
        assert "待审核知识" in text, f"{host}/ingest/SKILL.md missing 待审核知识"
        assert "/promote" in text, f"{host}/ingest/SKILL.md missing /promote"
        # Guided UX: internal IDs hidden from user-facing card
        assert "使用路径" not in text, (
            f"{host}/ingest/SKILL.md contains 使用路径 — provider chain should only "
            f"appear in result.json, not in the user-facing card"
        )


def test_claude_and_agents_ingest_skills_identical():
    """Claude and Agents ingest SKILL.md are byte-for-byte identical."""
    claude = _read_skill_text("claude")
    agents = _read_skill_text("agents")
    assert claude == agents, (
        "Claude and Agents ingest SKILL.md differ — they must be identical "
        f"(Claude: {len(claude)} chars, Agents: {len(agents)} chars)"
    )


# ── No oks-connector in installed skills (regression) ───────────────

def test_no_python_imports_in_ingest_skill():
    """Ingest SKILL.md has ZERO Python import references — Agent contract is oks CLI."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        assert "importlib.resources" not in text, (
            f"{host}/ingest/SKILL.md contains importlib.resources — should use oks schema show"
        )
        assert "from knowledge_studio" not in text, (
            f"{host}/ingest/SKILL.md contains from knowledge_studio import"
        )
        assert "oks-connector" not in text, (
            f"{host}/ingest/SKILL.md contains oks-connector"
        )
        assert "route_plan" not in text, (
            f"{host}/ingest/SKILL.md contains route_plan"
        )
        assert "oks schema show" in text, (
            f"{host}/ingest/SKILL.md missing oks schema show reference"
        )
        assert "oks ingest prepare" in text, (
            f"{host}/ingest/SKILL.md missing oks ingest prepare reference"
        )
        assert "oks security sanitize" in text, (
            f"{host}/ingest/SKILL.md missing oks security sanitize reference"
        )


# ── oks schema commands ─────────────────────────────────────────────
# These test the dynamic schema scanning, not the Agent behaviour.

def test_schema_list_dynamic_scan():
    """oks schema list scans the schemas/ directory and finds all 12 schemas."""
    from knowledge_studio.schema_examples import list_schema_names as examples_names
    from importlib.resources import files

    schemas_dir = files("knowledge_studio.schemas")
    all_names = sorted(
        e.name.replace(".schema.json", "")
        for e in schemas_dir.iterdir()
        if e.is_file() and e.name.endswith(".schema.json")
    )
    assert len(all_names) >= 10, f"Expected >=10 schemas, found {len(all_names)}"
    # Verify the 5 core schemas all have examples
    for name in examples_names():
        found = any(s.startswith(name) for s in all_names)
        assert found, f"Example schema '{name}' not in actual schemas: {all_names}"


def test_schema_examples_are_valid():
    """All 5 pre-built examples have required fields."""
    from knowledge_studio.schema_examples import get_example, list_schema_names

    for name in list_schema_names():
        ex = get_example(name)
        assert ex is not None, f"No example for {name}"
        assert isinstance(ex, dict), f"Example for {name} is not a dict"
        # locator is a referenced (embedded) schema — no top-level schema_version
        if name != "locator":
            assert "schema_version" in ex, f"Example for {name} missing schema_version"


def test_schema_show_resolves_names():
    """_resolve_schema_name finds schemas by short name and prefix."""
    from knowledge_studio.cli import _resolve_schema_name

    # Exact match
    result = _resolve_schema_name("source-envelope-v0.1")
    assert result is not None
    assert result[0] == "source-envelope-v0.1"

    # Prefix match
    result = _resolve_schema_name("evidence-manifest")
    assert result is not None
    assert "evidence-manifest" in result[0]

    # Not found
    assert _resolve_schema_name("nonexistent-schema") is None


# ── oks ingest prepare ──────────────────────────────────────────────

def test_ingest_prepare_text_creates_valid_envelope(tmp_path):
    """oks ingest prepare for a .md file creates valid source-envelope.json."""
    from knowledge_studio.ingest_prepare import prepare_ingest
    import json

    f = tmp_path / "test.md"
    f.write_text("# Hello OKS\n\nSample content for testing.", encoding="utf-8")

    result = prepare_ingest(str(f), kb_root=tmp_path)
    assert result["modality"] == "text"
    assert result["text_ready"] is True
    assert result["source_id"].startswith("src-")

    # Read the generated envelope
    env_path = tmp_path / ".oks" / "runs" / result["run_id"] / "manifest" / "source-envelope.json"
    assert env_path.is_file()
    envelope = json.loads(env_path.read_text(encoding="utf-8"))
    assert envelope["schema_version"] == "oks-source-envelope/v0.1"
    assert envelope["source_modality"] == "text"
    assert len(envelope["content_hash"]) == 64

    # Read the generated manifest
    man_path = tmp_path / ".oks" / "runs" / result["run_id"] / "manifest" / "evidence-manifest.json"
    assert man_path.is_file()
    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert len(manifest["evidence_records"]) == 1
    assert manifest["evidence_records"][0]["method"] == "text-read"

    # Clean up
    import shutil, stat
    def rm(p, f, e):
        import pathlib
        pathlib.Path(p).chmod(stat.S_IWRITE)
        f(p)
    shutil.rmtree(tmp_path / ".oks", onexc=rm)


def test_ingest_prepare_non_text_creates_skeleton(tmp_path):
    """oks ingest prepare for a .pdf file creates a skeleton (text_ready=False)."""
    from knowledge_studio.ingest_prepare import prepare_ingest
    import json

    f = tmp_path / "paper.pdf"
    f.write_bytes(b"%PDF-1.4 mock")

    result = prepare_ingest(str(f), kb_root=tmp_path)
    assert result["modality"] == "pdf"
    assert result["text_ready"] is False

    man_path = tmp_path / ".oks" / "runs" / result["run_id"] / "manifest" / "evidence-manifest.json"
    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "partial"
    assert manifest["evidence_records"] == []

    import shutil, stat
    def rm(p, f, e):
        import pathlib
        pathlib.Path(p).chmod(stat.S_IWRITE)
        f(p)
    shutil.rmtree(tmp_path / ".oks", onexc=rm)


# ── oks security sanitize ───────────────────────────────────────────

def test_security_sanitize_strips_api_key(tmp_path):
    """oks security sanitize removes API keys from JSON content."""
    from knowledge_studio.security.redaction import sanitize_remote_artifact

    content = b'{"api_key": "sk-secret-12345", "data": "public"}'
    result = sanitize_remote_artifact(content, content_type="application/json")
    assert b"sk-secret-12345" not in result
    assert b'"data": "public"' in result


def test_security_sanitize_preserves_binary(tmp_path):
    """Binary files are returned unchanged."""
    from knowledge_studio.security.redaction import sanitize_remote_artifact

    content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    result = sanitize_remote_artifact(content, content_type="image/png")
    assert result == content


# ── Integration: prepare → raw_commit ────────────────────────────────

def test_prepare_text_then_raw_commit_default_output(monkeypatch, tmp_path):
    """Integration: clean KB → prepare Markdown → raw-commit (no explicit output).

    Uses OKS_ROOT to redirect repo_root() into tmp_path so the *real*
    default-output codepath is exercised — including the P0-1 fix that
    creates the date-based parent directory before mkdtemp.
    """
    import json
    import os
    import shutil
    import stat as _stat

    from knowledge_studio.ingest_prepare import prepare_ingest
    from knowledge_studio.raw_commit import raw_commit, CommitError

    # 1. Redirect OKS_ROOT so default output lands under tmp_path
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))

    # 2. Create test markdown
    f = tmp_path / "test.md"
    f.write_text("# Integration Test\n\nContent for raw-commit.", encoding="utf-8")

    # 3. prepare_ingest()
    result = prepare_ingest(str(f), kb_root=tmp_path)
    assert result["text_ready"] is True
    manifest_dir = result["manifest_dir"]
    content_hash = result["content_hash"]

    # 4. raw_commit with NO output= argument — exercises default path
    commit_result = raw_commit(manifest_dir)
    assert commit_result["status"] == "committed"

    # 5. Verify default path: raw/YYYY/MM/DD/agent-capture/bundle-{hash[:16]}
    bundle_path = Path(commit_result["bundle_path"])
    assert bundle_path.is_dir()
    assert bundle_path.is_relative_to(tmp_path), (
        f"Bundle should be under tmp_path (OKS_ROOT), got {bundle_path}"
    )
    expected_prefix = f"bundle-{content_hash[:16]}"
    assert bundle_path.name == expected_prefix, (
        f"Expected bundle dir name {expected_prefix}, got {bundle_path.name}"
    )
    date_parents = bundle_path.relative_to(tmp_path)
    # raw/YYYY/MM/DD/agent-capture/bundle-xxx
    assert date_parents.parts[0] == "raw"
    assert date_parents.parts[-2] == "agent-capture"

    # 6. Verify bundle contents
    bundle_json_path = bundle_path / "bundle.json"
    assert bundle_json_path.is_file()
    bundle = json.loads(bundle_json_path.read_text(encoding="utf-8"))
    assert bundle["schema_version"] == "raw-multimodal/v0.2"

    content_md = bundle_path / "content.md"
    assert content_md.is_file()
    assert "Integration Test" in content_md.read_text(encoding="utf-8")

    # 7. Clean up
    def _rm(p, f, e):
        Path(p).chmod(_stat.S_IWRITE)
        f(p)
    shutil.rmtree(tmp_path / ".oks", onexc=_rm)
    shutil.rmtree(tmp_path / "raw", onexc=_rm)


# ── raw_commit error collection ──────────────────────────────────────

def test_raw_commit_reports_all_schema_errors(tmp_path):
    """raw_commit with bad envelope AND bad manifest reports ALL errors, not just first."""
    import json
    from knowledge_studio.raw_commit import raw_commit, CommitError

    manifest_dir = tmp_path / "manifest"
    artifacts_dir = manifest_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)

    # Bad envelope: missing required fields (no source_id, no content_hash, no schema_version)
    (manifest_dir / "source-envelope.json").write_text(json.dumps({
        "schema_version": "wrong-version",
    }), encoding="utf-8")

    # Bad manifest: missing required fields (no source_id, no primary_artifact)
    (manifest_dir / "evidence-manifest.json").write_text(json.dumps({
        "schema_version": "also-wrong",
    }), encoding="utf-8")

    try:
        raw_commit(manifest_dir)
        assert False, "Should have raised CommitError"
    except CommitError as exc:
        assert exc.code == "VALIDATION_FAILED"
        errors = exc.details.get("errors", [])
        # At least 2 errors: one from envelope, one from manifest
        assert len(errors) >= 2, (
            f"Expected >=2 errors, got {len(errors)}: {errors}"
        )
        codes = {e["code"] for e in errors}
        assert "INVALID_ENVELOPE" in codes, f"No envelope error in: {codes}"
        assert "INVALID_MANIFEST" in codes, f"No manifest error in: {codes}"


def test_raw_commit_schema_error_blocks_semantic_checks(tmp_path):
    """When envelope lacks source_id, cross_check is SKIPPED — no KeyError crash."""
    import json
    from knowledge_studio.raw_commit import raw_commit, CommitError

    manifest_dir = tmp_path / "manifest"
    artifacts_dir = manifest_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)

    # Envelope without source_id — schema will reject it
    (manifest_dir / "source-envelope.json").write_text(json.dumps({
        "schema_version": "oks-source-envelope/v0.1",
        "source_uri": "file:///nonexistent",
        "source_modality": "text",
        "access_mode": "local_file",
        "captured_at": "2026-01-01T00:00:00Z",
        "captured_by": {"runtime": "test"},
        "content_hash": "a" * 64,
    }), encoding="utf-8")

    # Manifest without source_id — schema will reject it too
    (manifest_dir / "evidence-manifest.json").write_text(json.dumps({
        "schema_version": "oks-evidence-manifest/v0.1",
        "manifest_id": "man-test",
    }), encoding="utf-8")

    try:
        raw_commit(manifest_dir)
        assert False, "Should have raised CommitError"
    except CommitError as exc:
        assert exc.code == "VALIDATION_FAILED"
        errors = exc.details.get("errors", [])
        codes = {e["code"] for e in errors}
        # Critical: must NOT contain MANIFEST_SOURCE_MISMATCH or other
        # semantic error codes — _cross_check was never reached.
        assert "MANIFEST_SOURCE_MISMATCH" not in codes, (
            f"_cross_check should be skipped when schemas fail. Got: {codes}"
        )
        # Only schema-level errors
        for code in codes:
            assert code in ("INVALID_ENVELOPE", "INVALID_MANIFEST"), (
                f"Unexpected error code: {code}"
            )


def test_raw_commit_missing_primary_artifact(tmp_path):
    """When manifest lacks primary_artifact, _check_artifacts skipped — no KeyError."""
    import json
    from knowledge_studio.raw_commit import raw_commit, CommitError

    manifest_dir = tmp_path / "manifest"
    artifacts_dir = manifest_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)

    # Valid envelope
    (manifest_dir / "source-envelope.json").write_text(json.dumps({
        "schema_version": "oks-source-envelope/v0.1",
        "source_id": "src-test",
        "source_uri": "file:///test.md",
        "source_modality": "text",
        "access_mode": "local_file",
        "captured_at": "2026-01-01T00:00:00Z",
        "captured_by": {"runtime": "test"},
        "content_hash": "a" * 64,
    }), encoding="utf-8")

    # Manifest without primary_artifact — schema will reject it
    (manifest_dir / "evidence-manifest.json").write_text(json.dumps({
        "schema_version": "oks-evidence-manifest/v0.1",
        "manifest_id": "man-test",
        "source_id": "src-test",
        "status": "complete",
        "evidence_records": [],
        "modalities": {},
    }), encoding="utf-8")

    try:
        raw_commit(manifest_dir)
        assert False, "Should have raised CommitError"
    except CommitError as exc:
        assert exc.code == "VALIDATION_FAILED"
        errors = exc.details.get("errors", [])
        codes = {e["code"] for e in errors}
        # Must NOT contain MISSING_ARTIFACT or ORPHAN_EVIDENCE —
        # semantic checks were skipped.
        for banned in ("MISSING_ARTIFACT", "ORPHAN_EVIDENCE", "EVIDENCE_COUNT_MISMATCH"):
            assert banned not in codes, (
                f"Semantic check {banned} should be skipped when manifest schema fails"
            )
        assert "INVALID_MANIFEST" in codes


# ── Phase 3A-S: Secret sanitization ──────────────────────────────────

def test_text_ready_sanitizes_api_key(tmp_path):
    """Source with Bearer token + api_key=value: evidence and artifacts MUST NOT contain secrets."""
    from knowledge_studio.ingest_prepare import prepare_ingest
    import json

    f = tmp_path / "secrets.md"
    f.write_text(
        "# Doc\n\n"
        "Authorization: Bearer sk-test-1234567890abcdef\n\n"
        "api_key: sk-test-token-value-here\n\n"
        "Normal content.\n",
        encoding="utf-8",
    )

    result = prepare_ingest(str(f), kb_root=tmp_path)
    assert result["text_ready"] is True
    assert result["sensitive_content_redacted"] is True
    assert result["redaction_count"] > 0

    # Check artifact — must NOT contain the secret
    art_path = tmp_path / ".oks" / "runs" / result["run_id"] / "manifest" / "artifacts" / "content.md"
    art_content = art_path.read_text(encoding="utf-8")
    assert "sk-test-1234567890abcdef" not in art_content
    assert "sk-test-token-value-here" not in art_content
    assert "***REDACTED***" in art_content

    # Check evidence-manifest.json — must NOT contain the secret
    man_path = tmp_path / ".oks" / "runs" / result["run_id"] / "manifest" / "evidence-manifest.json"
    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    assert manifest["notes"].get("sensitive_content_redacted") is True
    assert manifest["notes"].get("redaction_count", 0) > 0
    for rec in manifest["evidence_records"]:
        if "text" in rec:
            assert "sk-test-1234567890abcdef" not in rec["text"]
            assert "sk-test-token-value-here" not in rec["text"]

    import shutil, stat
    def rm(p, fn, ex): Path(p).chmod(stat.S_IWRITE); fn(p)
    shutil.rmtree(tmp_path / ".oks", onexc=rm)


def test_text_ready_preserves_source_file(tmp_path):
    """Original source file is NEVER modified by sanitization."""
    from knowledge_studio.ingest_prepare import prepare_ingest

    f = tmp_path / "secret-src.md"
    original = "# Secret doc\n\nBearer sk-test-abcdef1234567890\n"
    f.write_text(original, encoding="utf-8")

    prepare_ingest(str(f), kb_root=tmp_path)

    # Source file must be byte-identical to what we wrote
    assert f.read_text(encoding="utf-8") == original

    import shutil, stat
    def rm(p, fn, ex): Path(p).chmod(stat.S_IWRITE); fn(p)
    shutil.rmtree(tmp_path / ".oks", onexc=rm)


def test_text_ready_no_secrets_passes_through(tmp_path):
    """Plain text with no secrets: sensitive_content_redacted=False, content unchanged."""
    from knowledge_studio.ingest_prepare import prepare_ingest

    f = tmp_path / "clean.md"
    original = "# Clean doc\n\nNothing sensitive here.\n"
    f.write_text(original, encoding="utf-8")

    result = prepare_ingest(str(f), kb_root=tmp_path)
    assert result["text_ready"] is True
    assert result["sensitive_content_redacted"] is False
    assert result["redaction_count"] == 0

    # Content should be unchanged (no "***REDACTED***")
    art_path = tmp_path / ".oks" / "runs" / result["run_id"] / "manifest" / "artifacts" / "content.md"
    art_content = art_path.read_text(encoding="utf-8")
    assert "Nothing sensitive here" in art_content
    assert "***REDACTED***" not in art_content

    import shutil, stat
    def rm(p, fn, ex): Path(p).chmod(stat.S_IWRITE); fn(p)
    shutil.rmtree(tmp_path / ".oks", onexc=rm)


def test_text_ready_sanitizes_dashscope_key(tmp_path):
    """Source with bare DashScope sk- key (no Bearer prefix): MUST be caught."""
    from knowledge_studio.ingest_prepare import prepare_ingest
    import json

    f = tmp_path / "dashscope.md"
    f.write_text(
        "# API 配置\n\n"
        "阿里云百炼 API Key：sk-c0b1f0123456789abcdef0123456789abcd\n\n"
        "配置方式见下文。\n",
        encoding="utf-8",
    )

    result = prepare_ingest(str(f), kb_root=tmp_path)
    assert result["sensitive_content_redacted"] is True, (
        f"sk- DashScope key should be caught, got redacted={result['sensitive_content_redacted']}"
    )
    assert result["redaction_count"] > 0

    # Artifact must NOT contain the secret
    art_path = tmp_path / ".oks" / "runs" / result["run_id"] / "manifest" / "artifacts" / "content.md"
    art_content = art_path.read_text(encoding="utf-8")
    assert "sk-c0b1f0123456789abcdef0123456789abcd" not in art_content
    assert "***REDACTED***" in art_content

    # Source file must be unmodified
    assert "sk-c0b1f0123456789abcdef0123456789abcd" in f.read_text(encoding="utf-8")

    import shutil, stat
    def rm(p, fn, ex): Path(p).chmod(stat.S_IWRITE); fn(p)
    shutil.rmtree(tmp_path / ".oks", onexc=rm)


def test_redact_text_catches_bare_sk_key():
    """redact_text must catch a bare sk- prefix key without any label prefix."""
    from knowledge_studio.security.redaction import redact_text

    text = "我的密钥是 sk-proj-abc123xyz789def456ghi012jkl345mno"
    result = redact_text(text)
    assert "sk-proj-abc123xyz789def456ghi012jkl345mno" not in result
    assert "***REDACTED***" in result


def test_redact_text_catches_api_key_with_space():
    """'API Key: value' (with space between API and Key) must be caught."""
    from knowledge_studio.security.redaction import redact_text

    text = "API Key: sk-secret-value-12345"
    result = redact_text(text)
    assert "sk-secret-value-12345" not in result
    assert "***REDACTED***" in result


# ── Phase 3A-S: Markdown image detection ─────────────────────────────

def test_text_ready_no_images_is_complete(tmp_path):
    """Plain text with no image references: status stays complete."""
    from knowledge_studio.ingest_prepare import prepare_ingest

    f = tmp_path / "plain.md"
    f.write_text("# No images here\n\nJust plain text.", encoding="utf-8")

    result = prepare_ingest(str(f), kb_root=tmp_path)
    assert result["status"] == "complete"
    assert result["missing_assets"] == []

    import shutil, stat
    def rm(p, fn, ex): Path(p).chmod(stat.S_IWRITE); fn(p)
    shutil.rmtree(tmp_path / ".oks", onexc=rm)


def test_text_ready_missing_local_images_is_partial(tmp_path):
    """Markdown with ![](nonexistent.png): status=partial, missing_assets populated."""
    from knowledge_studio.ingest_prepare import prepare_ingest
    import json

    f = tmp_path / "with-images.md"
    f.write_text("# Doc with images\n\n![](missing1.png)\n\nSome text.\n\n![](also-gone.jpg)\n", encoding="utf-8")

    result = prepare_ingest(str(f), kb_root=tmp_path)
    assert result["status"] == "partial"
    assert len(result["missing_assets"]) == 2
    assert "missing1.png" in result["missing_assets"]
    assert "also-gone.jpg" in result["missing_assets"]

    # Verify manifest has failure_disposition set (required for raw_commit)
    man_path = tmp_path / ".oks" / "runs" / result["run_id"] / "manifest" / "evidence-manifest.json"
    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "partial"
    assert manifest["failure_disposition"] == "needs_user_action"
    assert "missing_assets" in manifest["notes"]
    assert "missing_assets_note" in manifest["notes"]
    # Text content still preserved
    assert "Some text" in manifest["evidence_records"][0]["text"]

    import shutil, stat
    def rm(p, fn, ex): Path(p).chmod(stat.S_IWRITE); fn(p)
    shutil.rmtree(tmp_path / ".oks", onexc=rm)


def test_text_ready_url_images_stays_complete(tmp_path):
    """Markdown with URL-based images: status stays complete (no remote check)."""
    from knowledge_studio.ingest_prepare import prepare_ingest

    f = tmp_path / "url-images.md"
    f.write_text("# Remote images\n\n![](https://example.com/img.png)\n\n![](http://cdn.io/photo.jpg)\n", encoding="utf-8")

    result = prepare_ingest(str(f), kb_root=tmp_path)
    assert result["status"] == "complete"
    assert result["missing_assets"] == []

    import shutil, stat
    def rm(p, fn, ex): Path(p).chmod(stat.S_IWRITE); fn(p)
    shutil.rmtree(tmp_path / ".oks", onexc=rm)


# ── Phase 3A-S: SKILL.md integrity ───────────────────────────────────

def test_promote_skill_has_no_invalid_params():
    """Installed promote SKILL.md must NOT reference --title, --type, or --area."""
    from importlib.resources import files

    for host in ("claude", "agents"):
        text = (
            files("knowledge_studio.skill_templates")
            .joinpath(host, "skills", "promote", "SKILL.md")
            .read_text(encoding="utf-8")
        )
        assert "--title" not in text, f"{host}/promote/SKILL.md references --title"
        assert "--type" not in text, f"{host}/promote/SKILL.md references --type"
        assert "--area" not in text, f"{host}/promote/SKILL.md references --area"
        # The actual command should be present
        assert "oks drafts promote" in text, f"{host}/promote/SKILL.md missing oks drafts promote"


def test_ingest_skill_candidate_not_schema():
    """Ingest SKILL.md must explicitly state Candidate is NOT a schema."""
    from importlib.resources import files

    for host in ("claude", "agents"):
        text = (
            files("knowledge_studio.skill_templates")
            .joinpath(host, "skills", "ingest", "SKILL.md")
            .read_text(encoding="utf-8")
        )
        assert "Candidate is NOT an OKS protocol schema" in text, (
            f"{host}/ingest/SKILL.md missing Candidate-is-not-schema statement"
        )
        # Must also explicitly forbid oks schema show candidate
        assert "Do NOT call" in text, (
            f"{host}/ingest/SKILL.md missing Do NOT call warning"
        )


# ── Phase 3A-S: Integration (prepare → raw_commit) ──────────────────

def test_full_sanitize_integration(monkeypatch, tmp_path):
    """Full pipeline: prepare → raw_commit, verify bundle is clean of secrets."""
    import json, shutil, stat as _stat
    from knowledge_studio.ingest_prepare import prepare_ingest
    from knowledge_studio.raw_commit import raw_commit

    monkeypatch.setenv("OKS_ROOT", str(tmp_path))

    f = tmp_path / "secret-doc.md"
    f.write_text(
        "# Doc\n\n"
        "Authorization: Bearer sk-test-sensitive-12345\n\n"
        "Token: Bearer eyJhbGciOiJIUzI1NiJ9.e30.ZrRHA1JJJW8opsbCGfG_HACGp2UMN1mNRpXjQ\n\n"
        "Normal content.\n",
        encoding="utf-8",
    )

    result = prepare_ingest(str(f), kb_root=tmp_path)
    assert result["text_ready"] is True
    assert result["sensitive_content_redacted"] is True

    commit_result = raw_commit(result["manifest_dir"])
    assert commit_result["status"] == "committed"

    bundle_path = Path(commit_result["bundle_path"])

    # content.md must be clean
    content_md = (bundle_path / "content.md").read_text(encoding="utf-8")
    assert "sk-test-sensitive-12345" not in content_md
    assert "eyJhbGciOiJIUzI1NiJ9" not in content_md

    # evidence.jsonl must be clean
    evidence = (bundle_path / "evidence.jsonl").read_text(encoding="utf-8")
    assert "sk-test-sensitive-12345" not in evidence
    assert "eyJhbGciOiJIUzI1NiJ9" not in evidence

    # source-envelope snapshot must also be clean
    env_path = bundle_path / "source-envelope.json"
    env = json.loads(env_path.read_text(encoding="utf-8"))
    assert "sk-test-sensitive" not in json.dumps(env)

    # Cleanup
    def _rm(p, fn, ex):
        Path(p).chmod(_stat.S_IWRITE)
        fn(p)
    shutil.rmtree(tmp_path / ".oks", onexc=_rm)
    shutil.rmtree(tmp_path / "raw", onexc=_rm)


# ══════════════════════════════════════════════════════════════════════
# Phase 3A-M — Dynamic Extraction + Guided UX automated tests
# ══════════════════════════════════════════════════════════════════════


# ── 1. Provider declares multiple capabilities ──────────────────────

def test_provider_declares_multiple_capabilities():
    """A single provider.yaml must be able to declare multiple capabilities."""
    from knowledge_studio.capability_commands import capability_list

    catalog = capability_list()
    # Check known multi-capability providers
    firecrawl = next(p for p in catalog["providers"] if p["id"] == "firecrawl")
    assert len(firecrawl["actions"]) >= 3, (
        f"firecrawl should declare >=3 capabilities, has {len(firecrawl['actions'])}"
    )

    agent_runtime = next(p for p in catalog["providers"] if p["id"] == "agent-runtime")
    assert len(agent_runtime["actions"]) >= 3, (
        f"agent-runtime should declare >=3 capabilities, has {len(agent_runtime['actions'])}"
    )

    pdf_lite = next(p for p in catalog["providers"] if p["id"] == "pdf-lite")
    assert len(pdf_lite["actions"]) >= 2, (
        f"pdf-lite should declare >=2 capabilities, has {len(pdf_lite['actions'])}"
    )


# ── 2. One provider can satisfy multiple demands ────────────────────

def test_one_provider_satisfies_multiple_demands():
    """One provider's capabilities can cover multiple Recipe demands."""
    from knowledge_studio.capability_commands import capability_list, capability_status

    catalog = capability_list()
    # web Recipe demands: web.fetch, web.extract (both required)
    # A single Firecrawl execution satisfies both
    web_providers = catalog["by_action"].get("web.fetch", [])
    extract_providers = catalog["by_action"].get("web.extract", [])
    # Firecrawl must appear in BOTH lists (one provider → multiple capabilities)
    assert "firecrawl" in web_providers, "firecrawl missing from web.fetch"
    assert "firecrawl" in extract_providers, "firecrawl missing from web.extract"
    # Same for agent-runtime: image.observe + layout.understand + chart.interpret
    assert "agent-runtime" in catalog["by_action"].get("image.observe", [])
    assert "agent-runtime" in catalog["by_action"].get("layout.understand", [])


# ── 3. Agent can get current availability facts ─────────────────────

def test_capability_status_returns_availability():
    """capability_status() must return provider availability, not just mapping."""
    from knowledge_studio.capability_commands import capability_status

    result = capability_status()
    assert "providers" in result
    assert "actions" in result
    assert "by_action" in result
    assert "overall" in result

    for p in result["providers"]:
        assert "status" in p, f"provider {p['id']} missing status"
        assert "healthy" in p, f"provider {p['id']} missing healthy"
        assert p["status"] in (
            "ready", "not_configured", "unavailable", "runtime_only",
            "blocked", "experimental",
        ), f"provider {p['id']} has unknown status: {p['status']}"
        assert "capabilities" in p, f"provider {p['id']} missing capabilities list"
        assert "known_limits" in p, f"provider {p['id']} missing known_limits"


def test_capability_status_actions_have_chinese_labels():
    """Every action in capability_status must have a Chinese label."""
    from knowledge_studio.capability_commands import capability_status

    result = capability_status()
    for name, info in result["actions"].items():
        assert info.get("label"), f"action '{name}' has empty label"
        # Labels should contain non-ASCII (Chinese) characters
        assert info["label"] != name, (
            f"action '{name}' label equals its id — should have Chinese name"
        )


# ── 4. required / optional demand distinction in Recipes ────────────

def test_recipes_have_required_and_optional_capabilities():
    """Every Recipe must distinguish required from optional capabilities."""
    from importlib.resources import files

    recipes_dir = files("knowledge_studio.recipes")
    recipe_names = [
        "text.md", "pdf.md", "web.md", "office.md",
        "image.md", "audio.md", "video.md",
    ]
    for name in recipe_names:
        recipe_path = recipes_dir.joinpath(name)
        assert recipe_path.is_file(), f"recipe missing: {name}"
        text = recipe_path.read_text(encoding="utf-8")
        assert "required_capabilities" in text, (
            f"{name} missing required_capabilities"
        )
        assert "optional_capabilities" in text, (
            f"{name} missing optional_capabilities"
        )


# ── 5. Missing required → cannot silently complete ──────────────────

def test_ingest_skill_forbids_silent_partial_promotion():
    """Ingest SKILL.md must say: missing required → partial, not complete."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        assert "NEVER upgrade partial to complete" in text, (
            f"{host}/ingest/SKILL.md missing: NEVER upgrade partial to complete"
        )
        # Must describe what happens when required is missing
        assert "required" in text.lower(), (
            f"{host}/ingest/SKILL.md must reference required capabilities"
        )


def test_ingest_skill_guides_partial_to_user():
    """When evidence is partial, Agent must explain impact and recommend action."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        assert "推荐" in text, (
            f"{host}/ingest/SKILL.md missing 推荐 (recommendation) in user-facing card"
        )
        assert "影响" in text, (
            f"{host}/ingest/SKILL.md missing 影响 (impact) in user-facing card"
        )


# ── 6. Agent Runtime provenance ─────────────────────────────────────

def test_ingest_skill_labels_agent_observation():
    """Agent observation must be labeled as agent_observed, not mechanical."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        assert "agent_observed" in text, (
            f"{host}/ingest/SKILL.md missing agent_observed provenance"
        )
        assert "agent_multimodal_observation" in text, (
            f"{host}/ingest/SKILL.md missing agent_multimodal_observation method"
        )
        assert "NEVER present agent inference as source text" in text, (
            f"{host}/ingest/SKILL.md missing agent inference constraint"
        )


def test_agent_runtime_provider_declares_evidence_provenance():
    """agent-runtime provider.yaml must declare evidence method and agent_judgment."""
    from knowledge_studio.capability_commands import _scan_providers
    from knowledge_studio.capability_commands import _providers_root

    providers = _scan_providers(_providers_root())
    ar = next(p for p in providers if p.get("id") == "agent-runtime")
    evidence = ar.get("evidence", {})
    assert evidence.get("agent_judgment") == "agent_observed", (
        "agent-runtime must declare agent_judgment: agent_observed"
    )
    assert evidence.get("method") == "agent_multimodal_observation", (
        "agent-runtime must declare method: agent_multimodal_observation"
    )


# ── 7. 用户视图中文化 ──────────────────────────────────────────────

def test_user_facing_text_is_chinese():
    """All user-facing UI text must be in Chinese natural language."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        # Check the Guided UX Principles section has Chinese examples
        assert "用户做判断" in text or "Ask users for judgment" in text, (
            f"{host}/ingest/SKILL.md missing Guided UX principles"
        )


def test_i18n_has_chinese_for_all_keys():
    """Every i18n key must have a zh (Chinese) translation."""
    from knowledge_studio.i18n import _TEXTS

    for key, entry in _TEXTS.items():
        assert "zh" in entry, f"i18n key '{key}' missing zh translation"
        assert entry["zh"], f"i18n key '{key}' has empty zh translation"


# ── 8. internal capability ID default hidden ────────────────────────

def test_init_summary_hides_internal_ids():
    """User-facing capability descriptions must NOT expose internal provider IDs.

    The raw label (without install hints) must be free of internal IDs.
    Install hints like 'oks capability install pdf-lite' or 'pip install
    markitdown' are actionable instructions — those may reference IDs because
    that's what the user actually types.  The capability label itself must
    be in plain Chinese (e.g. 'PDF 文本提取', not 'pdf-lite')."""
    from knowledge_studio.capability_commands import (
        _USER_CAPABILITY_LABELS,
        _describe_ready_capabilities,
        _build_capability_summary,
        capability_doctor,
    )

    doctor = capability_doctor()
    summary = _build_capability_summary(doctor)
    can_do, can_enable = _describe_ready_capabilities(summary)

    internal_ids = {
        "pdf-lite", "firecrawl", "agentkey", "rapidocr", "trafilatura",
        "yt-dlp", "ffmpeg", "mediacrawler", "agent-runtime", "text-read",
        "local-asr", "remote-asr", "mineru",
    }

    for label in can_do + can_enable:
        # Split off any install hint (after ' — ')
        capability_name = label.split(" — ")[0].strip()
        for pid in internal_ids:
            assert pid not in capability_name.lower(), (
                f"Capability label exposes internal ID '{pid}': '{capability_name}'"
            )


def test_init_summary_labels_are_defined():
    """Every provider in the catalog should appear in _USER_CAPABILITY_LABELS."""
    from knowledge_studio.capability_commands import (
        _USER_CAPABILITY_LABELS,
        _ALWAYS_AVAILABLE,
    )
    from knowledge_studio.capability_commands import capability_list
    from knowledge_studio.capability_commands import capability_doctor
    from knowledge_studio.capability_commands import _scan_providers, _providers_root

    # All non-always-available providers should have a user-facing label
    for p in _scan_providers(_providers_root()):
        pid = p.get("id", "")
        if pid in _ALWAYS_AVAILABLE:
            continue
        assert pid in _USER_CAPABILITY_LABELS, (
            f"Provider '{pid}' missing from _USER_CAPABILITY_LABELS"
        )


# ── 9. Provider does not write to Raw directly ──────────────────────

def test_normalize_functions_return_fragment_not_write():
    """normalize.py functions are pure — they return dicts, don't write files."""
    import inspect

    normalize_modules = [
        "knowledge_studio.providers.firecrawl.normalize",
        "knowledge_studio.providers.agentkey.normalize",
        "knowledge_studio.providers.text_read.normalize",
        "knowledge_studio.providers.pdf_lite.normalize",
        "knowledge_studio.providers.markitdown.normalize",
        "knowledge_studio.providers.rapidocr.normalize",
        "knowledge_studio.providers.yt_dlp.normalize",
        "knowledge_studio.providers.ffmpeg.normalize",
    ]
    for mod_name in normalize_modules:
        try:
            mod = __import__(mod_name, fromlist=["normalize"])
        except ImportError:
            continue  # not installed — skip
        fn = getattr(mod, "normalize", None)
        assert fn is not None, f"{mod_name} missing normalize function"
        sig = inspect.signature(fn)
        # normalize() must NOT have file-writing parameters like 'output_path'
        params = list(sig.parameters.keys())
        assert "output_path" not in params, (
            f"{mod_name}.normalize() has output_path param — it should be pure"
        )
        # Must have source_id as first param
        assert "source_id" in params, (
            f"{mod_name}.normalize() missing source_id parameter"
        )


def test_raw_commit_is_the_only_raw_writer():
    """Only raw_commit writes to raw/ — providers return fragments."""
    from knowledge_studio.raw_commit import raw_commit as _commit_fn
    import inspect

    # raw_commit function exists and is the sole path to raw/
    assert callable(_commit_fn)
    sig = inspect.signature(_commit_fn)
    # Takes manifest_dir, not individual fragments
    assert "manifest_dir" in sig.parameters


# ── 10. Human Review boundary unchanged ──────────────────────────────

def test_candidate_requires_human_review():
    """Candidate must go to drafts/ — Agent never writes to wiki/ directly."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        assert "NEVER write to wiki/ directly" in text, (
            f"{host}/ingest/SKILL.md missing: NEVER write to wiki/ directly"
        )
        assert "/promote" in text, (
            f"{host}/ingest/SKILL.md missing /promote — human review gate"
        )


def test_wiki_write_is_only_via_cli():
    """Wiki page creation must go through store.write_wiki_page, not raw file writes."""
    from knowledge_studio.store import write_wiki_page, promote_draft
    import inspect

    # These are the only two functions that write wiki pages
    assert callable(write_wiki_page)
    assert callable(promote_draft)
    # promote_draft is the gate from draft to wiki
    sig = inspect.signature(promote_draft)
    assert "slug" in sig.parameters


# ── Bonus: capability_status is the single source of truth ──────────

def test_capability_status_includes_mediacrawler():
    """MediaCrawler must appear in capability_status even though not installed."""
    from knowledge_studio.capability_commands import capability_status

    result = capability_status()
    mediacrawler = next(
        (p for p in result["providers"] if p["id"] == "mediacrawler"), None
    )
    assert mediacrawler is not None, "mediacrawler missing from capability_status"
    assert mediacrawler["status"] == "unavailable", (
        f"mediacrawler should be 'unavailable', got '{mediacrawler['status']}'"
    )
    assert "platforms" in mediacrawler or any(
        "platforms" in p for p in result["providers"] if p["id"] == "mediacrawler"
    ), "mediacrawler should have platform metadata"
    # Must provide social capabilities
    assert "social.content.fetch" in mediacrawler["capabilities"], (
        "mediacrawler must provide social.content.fetch"
    )


def test_capability_status_social_actions_exist():
    """Social capability actions added in Phase 3A-M must be present."""
    from knowledge_studio.capability_commands import capability_status

    result = capability_status()
    for action in (
        "social.content.fetch",
        "social.search",
        "social.comments.fetch",
        "social.creator.fetch",
    ):
        assert action in result["actions"], (
            f"social action '{action}' missing from capability_status"
        )
        # Must have a Chinese label different from the internal ID
        label = result["actions"][action]["label"]
        assert label != action, (
            f"social action '{action}' has no Chinese label"
        )


def test_capability_status_one_call_sufficiency():
    """capability_status must provide enough info for Agent to select providers
    WITHOUT needing additional capability catalog or doctor calls."""
    from knowledge_studio.capability_commands import capability_status

    result = capability_status()
    # Agent needs: actions with labels, providers with status, by_action mapping
    assert result["actions"], "actions must not be empty"
    assert result["providers"], "providers must not be empty"
    assert result["by_action"], "by_action mapping must not be empty"
    # Each provider must have enough info for decision-making
    for p in result["providers"]:
        assert "id" in p
        assert "status" in p
        assert "execution" in p
        assert "capabilities" in p
        assert len(p["capabilities"]) > 0, (
            f"provider {p['id']} has zero capabilities"
        )


# ══════════════════════════════════════════════════════════════════════
# Phase 3A-M 增量：优雅降级 (Graceful Degradation)
# ══════════════════════════════════════════════════════════════════════


def test_degradation_ladder_in_skill():
    """L0-L4 degradation levels must be documented in ingest SKILL.md."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        assert "L0" in text and "Preferred" in text, (
            f"{host}/ingest/SKILL.md missing L0 Preferred"
        )
        assert "L1" in text and "Automatic Fallback" in text, (
            f"{host}/ingest/SKILL.md missing L1 Automatic Fallback"
        )
        assert "L2" in text and "Honest Partial" in text, (
            f"{host}/ingest/SKILL.md missing L2 Honest Partial"
        )
        assert "L3" in text and "Guided Assistance" in text, (
            f"{host}/ingest/SKILL.md missing L3 Guided Assistance"
        )
        assert "L4" in text and "Cannot" in text, (
            f"{host}/ingest/SKILL.md missing L4 Cannot Reliably Extract"
        )


def test_graceful_degradation_principles_in_skill():
    """All 10 core degradation principles must appear as MUST constraints."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        principles = [
            "MUST follow L0",
            "MUST attempt auto-fallback",
            "MUST NOT block on missing optional capability",
            "MUST NOT fabricate evidence",
            "MUST aggregate all gaps",
            "MUST preserve provenance",
            "MUST stop capability escalation",
            "MUST provide a recommendation",
            "MUST explain each gap in terms of user impact",
            "MUST label all Agent-observed evidence as agent_observed",
        ]
        for p in principles:
            assert p in text, f"{host}/ingest/SKILL.md missing principle: {p}"


def test_optional_capability_does_not_block():
    """Missing optional capability must NEVER block the task."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        assert "optional means optional" in text, (
            f"{host}/ingest/SKILL.md must state 'optional means optional'"
        )
        assert "MUST NOT block on missing optional capability" in text, (
            f"{host}/ingest/SKILL.md missing optional-no-block constraint"
        )


def test_gap_aggregation_rule():
    """Multiple capability gaps must be aggregated into ONE user message."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        assert "MUST aggregate all gaps" in text, (
            f"{host}/ingest/SKILL.md missing gap aggregation MUST"
        )
        # Must mention aggregation format fields
        assert "已获得" in text, f"{host}/ingest/SKILL.md missing 已获得 in gap format"
        assert "仍缺" in text, f"{host}/ingest/SKILL.md missing 仍缺 in gap format"
        assert "影响" in text, f"{host}/ingest/SKILL.md missing 影响 in gap format"
        assert "推荐" in text, f"{host}/ingest/SKILL.md missing 推荐 in gap format"


def test_text_only_orchestrator_rule():
    """Text-only orchestrator must use Providers, never hallucinate multimodal."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        assert "Text-Only Orchestrator" in text or "text-only" in text.lower(), (
            f"{host}/ingest/SKILL.md missing text-only orchestrator guidance"
        )
        assert "NEVER hallucinate" in text, (
            f"{host}/ingest/SKILL.md missing NEVER hallucinate constraint"
        )
        # Must reference using registered Providers for missing modalities
        assert "Provider" in text, (
            f"{host}/ingest/SKILL.md must reference Providers for missing modalities"
        )


def test_degradation_stops_after_required():
    """Agent must stop escalating after required Evidence is satisfied."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        assert "MUST stop capability escalation" in text, (
            f"{host}/ingest/SKILL.md missing stop-escalation constraint"
        )
        assert "Stop escalating after required" in text, (
            f"{host}/ingest/SKILL.md missing stop-after-required rule"
        )


# ══════════════════════════════════════════════════════════════════════
# Gate 3A-M-R1: Capability Truthfulness & Safe Degradation
# ══════════════════════════════════════════════════════════════════════


# ── P0-1: CJK boundary credential leakage ──────────────────────────

def test_redact_text_catches_cjk_adjacent_sk_key():
    """sk- key immediately preceded by Chinese character (no space) MUST be caught.

    Python 3 \\w includes CJK characters via re.UNICODE (default), so \\b
    does NOT match at CJK→ASCII transitions — both sides are \\w chars.
    The fix replaces \b with (?<![a-zA-Z0-9_]) / (?![a-zA-Z0-9_]).
    """
    from knowledge_studio.security.redaction import redact_text

    # CJK character "为" immediately before sk- — no space
    cases = [
        "密钥为sk-proj-abc123xyz789def456ghi012jkl345mno",
        "API密钥：sk-c0b1f0123456789abcdef0123456789abcd",
        "设置sk-proj-0123456789abcdef0123456789abcdef为环境变量",
        "我的sk-admin-abcdef0123456789abcdef01234567密钥已配置",
    ]
    for text in cases:
        result = redact_text(text)
        assert "sk-" not in result, (
            f"CJK-adjacent sk- key NOT redacted!\n"
            f"  Input:  {text[:80]}...\n"
            f"  Output: {result[:80]}..."
        )
        assert "***REDACTED***" in result


def test_redact_text_cjk_boundary_all_patterns():
    """All SENSITIVE_PATTERNS must work when adjacent to CJK characters.

    This verifies the \b→ASCII-lookaround fix for every credential pattern.
    """
    from knowledge_studio.security.redaction import redact_text

    cjk_cases = [
        # CJK before Bearer
        ("令牌为Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123def456ghi789",
         "Bearer"),
        # CJK before JWT
        ("解析eyJhbGciOiJIUzI1NiJ9.eyJuYW1lIjoiSm9obiJ9.xJgfW6qcBzOJKFpYjH2TIA",
         "eyJ"),
        # CJK before Basic auth
        ("认证方式Basic dXNlcjpwYXNzd29yZA==",
         "Basic"),
        # CJK before API key pattern
        ("配置api_key=abcdef0123456789abcdef0123456789ab即可",
         "api_key"),
        # CJK before AWS key
        ("使用AKIAIOSFODNN7EXAMPLE后",
         "AKIA"),
    ]
    for text, credential_type in cjk_cases:
        result = redact_text(text)
        assert "***REDACTED***" in result, (
            f"CJK-adjacent {credential_type} NOT redacted!\n"
            f"  Input:  {text[:100]}\n"
            f"  Output: {result[:100]}"
        )


def test_root_and_package_sensitive_fields_identical():
    """Root security/sensitive_fields.py and package copy MUST be byte-identical."""
    root = Path(__file__).parent.parent.parent / "security" / "sensitive_fields.py"
    pkg = Path(__file__).parent.parent / "knowledge_studio" / "security" / "sensitive_fields.py"

    root_text = root.read_text(encoding="utf-8")
    pkg_text = pkg.read_text(encoding="utf-8")
    assert root_text == pkg_text, (
        f"Root and package sensitive_fields.py differ! "
        f"(root: {len(root_text)} chars, package: {len(pkg_text)} chars)"
    )


# ── P0-2: Agent multimodal not unconditionally available ────────────

def test_agent_runtime_is_runtime_only():
    """agent-runtime MUST be runtime_only — depends on current Agent model.

    Text-only orchestrators cannot perform multimodal capabilities.
    """
    from knowledge_studio.capability_commands import _provider_status

    status = _provider_status([], "agent-runtime", "agent_native")
    assert status == "runtime_only", (
        f"agent-runtime should be 'runtime_only', got '{status}'"
    )


def test_runtime_only_not_in_can_do():
    """runtime_only providers must NOT appear as 'available now' in init output."""
    from knowledge_studio.capability_commands import (
        _describe_ready_capabilities,
        _build_capability_summary,
    )

    doctor = {
        "overall": "issues_found",
        "providers": [
            {"id": "agentkey", "execution": "external", "status": "runtime_only",
             "label": "受限平台内容获取"},
            {"id": "agent-runtime", "execution": "agent_native", "status": "runtime_only",
             "label": "Agent 多模态理解"},
        ],
    }
    summary = _build_capability_summary(doctor)
    can_do, can_enable = _describe_ready_capabilities(summary)

    # agent-runtime is always-available-filtered — should be absent from both
    for label in can_do:
        assert "Agent" not in label, (
            f"agent-runtime should not appear in can_do: '{label}'"
        )
    # agentkey is runtime_only — should appear in can_enable, not can_do
    assert not any("受限平台" in label for label in can_do), (
        "runtime_only agentkey should not be in can_do"
    )
    assert any("受限平台" in label for label in can_enable), (
        "runtime_only agentkey should be in can_enable with caveat"
    )


def test_capability_status_agent_runtime_is_runtime_only():
    """capability_status must report agent-runtime as runtime_only, not ready."""
    from knowledge_studio.capability_commands import capability_status

    result = capability_status()
    ar = next((p for p in result["providers"] if p["id"] == "agent-runtime"), None)
    assert ar is not None, "agent-runtime missing from capability_status"
    assert ar["status"] == "runtime_only", (
        f"agent-runtime should be 'runtime_only', got '{ar['status']}'"
    )


# ── P1-1: Ordinary web fallback chain ───────────────────────────────

def test_agent_runtime_declares_web_fetch():
    """Agent Runtime must declare web.fetch — it can fetch public web pages."""
    from knowledge_studio.capability_commands import capability_list

    catalog = capability_list()
    ar = next(p for p in catalog["providers"] if p["id"] == "agent-runtime")
    assert "web.fetch" in ar["actions"], (
        "agent-runtime must provide web.fetch as a truthful fallback "
        "for ordinary public web pages"
    )


def test_http_fetch_is_experimental():
    """http-fetch must be consistently experimental across provider.yaml + status."""
    from knowledge_studio.capability_commands import _provider_status

    status = _provider_status([], "http-fetch", "managed")
    assert status == "experimental", (
        f"http-fetch should be 'experimental', got '{status}'"
    )


def test_http_fetch_provider_yaml_consistent():
    """http-fetch provider.yaml must declare experimental maturity, not stable."""
    from knowledge_studio.capability_commands import _scan_providers, _providers_root

    providers = _scan_providers(_providers_root())
    hf = next(p for p in providers if p.get("id") == "http-fetch")
    provides = hf.get("provides", {})
    for cap, info in provides.items():
        if isinstance(info, dict):
            maturity = info.get("maturity", "")
            assert maturity == "experimental", (
                f"http-fetch {cap} should be 'experimental', got '{maturity}'"
            )


# ── P1-2: Video Recipe subtitle/ASR fallback ────────────────────────

def test_video_recipe_allows_asr_substitute():
    """No subtitles + ASR success must satisfy video transcript requirement.

    subtitle.fetch (required) failure should NOT permanently partial the result
    when speech.transcribe (optional, ASR fallback) produces a valid transcript.
    The complete_when condition subtitles_or_transcript_available can be
    satisfied by EITHER subtitle.fetch OR speech.transcribe.

    Verifies: (a) required_capabilities only use real Registry IDs,
    (b) the degradation chain documents the ASR substitution,
    (c) complete_when accepts the transcript from either path.
    """
    from importlib.resources import files

    video_recipe = files("knowledge_studio.recipes").joinpath("video.md")
    text = video_recipe.read_text(encoding="utf-8")

    # transcript_or_subtitle is NOT a real capability — must not appear
    assert "transcript_or_subtitle" not in text, (
        "video.md must NOT contain the fake capability 'transcript_or_subtitle'. "
        "All required_capabilities and optional_capabilities must be real "
        "Capability Registry IDs."
    )
    # subtitle.fetch IS a real capability — must be in required
    assert "subtitle.fetch" in text, (
        "video.md required_capabilities must include subtitle.fetch "
        "(the real Registry capability, not a pseudo-capability)"
    )
    # The degradation note must document the substitution
    assert "speech.transcribe" in text, (
        "video.md degradation must reference speech.transcribe as fallback"
    )
    # complete_when already has subtitles_or_transcript_available
    assert "subtitles_or_transcript_available" in text, (
        "video.md complete_when missing subtitles_or_transcript_available"
    )


# ── Firecrawl metadata.fetch declaration ────────────────────────────

def test_firecrawl_declares_metadata_fetch():
    """Firecrawl provider.yaml must declare metadata.fetch.

    Ingest SKILL.md references Firecrawl metadata.fetch as part of the
    provider cluster (one /scrape → web.fetch + web.extract + metadata.fetch).
    The provider.yaml must match.
    """
    from knowledge_studio.capability_commands import capability_list

    catalog = capability_list()
    firecrawl = next(p for p in catalog["providers"] if p["id"] == "firecrawl")
    assert "metadata.fetch" in firecrawl["actions"], (
        "firecrawl must declare metadata.fetch — SKILL.md Step 4 references it "
        "as part of the 3-capability provider cluster"
    )


# ── MediaCrawler truthfulness ───────────────────────────────────────

def test_mediacrawler_all_experimental():
    """All MediaCrawler capabilities must be experimental — no validated claims.

    MediaCrawler OKS integration has never been independently verified.
    """
    from knowledge_studio.capability_commands import _scan_providers, _providers_root

    providers = _scan_providers(_providers_root())
    mc = next(p for p in providers if p.get("id") == "mediacrawler")
    provides = mc.get("provides", {})
    for cap, info in provides.items():
        if isinstance(info, dict):
            maturity = info.get("maturity", "")
            assert maturity == "experimental", (
                f"mediacrawler {cap} maturity='{maturity}' — "
                f"must be 'experimental' (OKS integration unverified)"
            )


def test_mediacrawler_skill_in_package():
    """MediaCrawler SKILL.md must exist in the package directory for wheel inclusion."""
    from importlib.resources import files

    skill_path = files("knowledge_studio.providers.mediacrawler").joinpath("SKILL.md")
    assert skill_path.is_file(), (
        "cli/knowledge_studio/providers/mediacrawler/SKILL.md missing — "
        "not included in wheel"
    )
    text = skill_path.read_text(encoding="utf-8")
    assert "experimental" in text.lower(), (
        "mediacrawler SKILL.md must reflect experimental (unverified) status"
    )


# ══════════════════════════════════════════════════════════════════════
# Gate 3A-M-R2: Agent-Facing Contract Closure
# ══════════════════════════════════════════════════════════════════════


# ── Recipe Capability Invariant ─────────────────────────────────────

def _parse_recipe_capability_list(text: str, section: str) -> list[str]:
    """Extract capability IDs from a YAML list section in a recipe.

    Handles the indented list format used in recipe markdown code blocks.
    """
    import re

    in_section = False
    caps: list[str] = []
    for line in text.splitlines():
        if line.strip() == f"{section}:":
            in_section = True
            continue
        if in_section:
            stripped = line.strip()
            if stripped.startswith("- "):
                cap = stripped[2:].strip()
                if cap:
                    caps.append(cap)
            elif stripped and not stripped.startswith("#") and not stripped.startswith("- "):
                # Next top-level key — exit the list
                if not line.startswith(" ") and not line.startswith("\t"):
                    break
    return caps


def test_recipe_capabilities_all_in_registry():
    """Every required_capability and optional_capability in every Recipe
    MUST exist in the Capability Registry (actions.yaml).

    This is an invariant — any pseudo-capability like 'transcript_or_subtitle'
    that doesn't correspond to a real Registry action must be caught here.
    """
    from importlib.resources import files

    # Load all real capability IDs from the Registry
    actions_yaml = files("knowledge_studio.capabilities").joinpath("actions.yaml")
    registry_text = actions_yaml.read_text(encoding="utf-8")
    # Parse actions from actions.yaml
    registry_ids: set[str] = set()
    in_actions = False
    for line in registry_text.splitlines():
        stripped = line.strip()
        if stripped == "actions:":
            in_actions = True
            continue
        if in_actions:
            if stripped and not line.startswith(" ") and not line.startswith("\t"):
                break  # next top-level key
            if stripped and not stripped.startswith("#"):
                # Action name is the key before the colon
                if ":" in stripped and not stripped.startswith("-"):
                    action_id = stripped.split(":")[0].strip()
                    if action_id:
                        registry_ids.add(action_id)

    assert len(registry_ids) >= 20, (
        f"Expected >=20 actions in Registry, found {len(registry_ids)}"
    )

    # Check every recipe
    recipes_dir = files("knowledge_studio.recipes")
    recipe_names = [
        "text.md", "pdf.md", "web.md", "office.md",
        "image.md", "audio.md", "video.md",
    ]
    violations: list[str] = []
    for name in recipe_names:
        recipe_path = recipes_dir.joinpath(name)
        assert recipe_path.is_file(), f"recipe missing: {name}"
        text = recipe_path.read_text(encoding="utf-8")

        required = _parse_recipe_capability_list(text, "required_capabilities")
        optional = _parse_recipe_capability_list(text, "optional_capabilities")
        all_caps = required + optional

        for cap in all_caps:
            if cap not in registry_ids:
                violations.append(f"{name}: '{cap}' not in Capability Registry")

    assert not violations, (
        f"Recipe capabilities not in Registry ({len(violations)} violations):\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


# ── Recipe in ingest prepare output ─────────────────────────────────

def test_ingest_prepare_includes_recipe(tmp_path):
    """oks ingest prepare output must include the Recipe for the detected modality.

    The Agent must be able to read the Recipe from the CLI output without
    needing a recipes/ directory in the user's knowledge base.
    """
    from knowledge_studio.ingest_prepare import prepare_ingest

    f = tmp_path / "test.pdf"
    f.write_bytes(b"%PDF-1.4 mock")

    result = prepare_ingest(str(f), kb_root=tmp_path)
    assert result["modality"] == "pdf"
    assert "recipe" in result, (
        "ingest prepare output missing 'recipe' field"
    )
    assert result["recipe"] is not None, (
        "ingest prepare recipe is None for pdf modality"
    )
    assert "Recipe: PDF" in result["recipe"], (
        "recipe should contain 'Recipe: PDF' header"
    )
    assert "required_capabilities" in result["recipe"], (
        "recipe must list required_capabilities"
    )

    import shutil, stat
    def rm(p, fn, ex): Path(p).chmod(stat.S_IWRITE); fn(p)
    shutil.rmtree(tmp_path / ".oks", onexc=rm)


def test_ingest_prepare_recipe_for_all_modalities(tmp_path):
    """Every known modality must have a recipe in the ingest prepare output."""
    from knowledge_studio.ingest_prepare import prepare_ingest

    test_files = {
        "text": ("test.md", "# Hello"),
        "pdf": ("test.pdf", b"%PDF-1.4"),
        "web": ("test.html", "<html><body>Test</body></html>"),
        "office": ("test.docx", b"PK\x03\x04"),
        "image": ("test.png", b"\x89PNG\r\n"),
        "audio": ("test.mp3", b"ID3\x03\x00"),
        "video": ("test.mp4", b"\x00\x00\x00\x18ftypmp42"),
    }
    for expected_modality, (filename, content) in test_files.items():
        f = tmp_path / filename
        if isinstance(content, str):
            f.write_text(content, encoding="utf-8")
        else:
            f.write_bytes(content)

        result = prepare_ingest(str(f), kb_root=tmp_path)
        assert result["modality"] == expected_modality, (
            f"{filename} should be {expected_modality}, got {result['modality']}"
        )
        assert result.get("recipe") is not None, (
            f"ingest prepare for {filename} ({expected_modality}) missing recipe"
        )
        assert len(result["recipe"]) > 50, (
            f"recipe for {expected_modality} is too short ({len(result['recipe'])} chars)"
        )

        import shutil, stat
        def rm(p, fn, ex): Path(p).chmod(stat.S_IWRITE); fn(p)
        shutil.rmtree(tmp_path / ".oks", onexc=rm)


# ── capability guide command ────────────────────────────────────────

def test_capability_guide_returns_skill_md():
    """oks capability guide <provider> returns the canonical SKILL.md content."""
    from importlib.resources import files

    # Test with providers that are known to have SKILL.md
    for provider in ("pdf-lite", "firecrawl", "agentkey"):
        skill_path = files("knowledge_studio.providers").joinpath(provider, "SKILL.md")
        if not skill_path.is_file():
            continue
        content = skill_path.read_text(encoding="utf-8")
        assert len(content) > 0, f"{provider} SKILL.md is empty"
        # Must contain the provider name
        assert provider in content.lower() or provider.replace("-", "") in content.lower(), (
            f"{provider} SKILL.md does not reference its own provider name"
        )


def test_capability_guide_all_providers_with_skill():
    """Every provider that has a SKILL.md must be accessible via capability guide."""
    from importlib.resources import files

    providers_root = files("knowledge_studio.providers")
    found = 0
    for entry in sorted(providers_root.iterdir()):
        if not entry.is_dir():
            continue
        skill_path = entry / "SKILL.md"
        if skill_path.is_file():
            content = skill_path.read_text(encoding="utf-8")
            assert len(content) > 100, (
                f"provider {entry.name} SKILL.md is too short ({len(content)} chars)"
            )
            found += 1
    assert found >= 10, (
        f"Expected >=10 providers with SKILL.md, found {found}"
    )


# ── Ingest SKILL.md: Agent-facing contract closure ──────────────────

def test_ingest_skill_uses_cli_for_recipe():
    """Ingest SKILL.md must tell Agent to get Recipe from oks ingest prepare,
    NOT to read recipes/{modality}.md from disk."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        # Must tell Agent to use the prepare output
        assert "recipe" in text.lower(), (
            f"{host}/ingest/SKILL.md must reference the recipe field"
        )
        # Must forbid reading from disk
        assert "Do NOT read `recipes/" in text or "does not contain a recipes/" in text, (
            f"{host}/ingest/SKILL.md must tell Agent NOT to read recipes/ from disk"
        )


def test_ingest_skill_uses_cli_for_provider_guide():
    """Ingest SKILL.md must tell Agent to use oks capability guide,
    NOT to read providers/.../SKILL.md from disk."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        assert "oks capability guide" in text, (
            f"{host}/ingest/SKILL.md must reference oks capability guide"
        )
        assert "Do NOT read `providers/" in text or "does not contain a providers/" in text, (
            f"{host}/ingest/SKILL.md must tell Agent NOT to read providers/ from disk"
        )


def test_ingest_skill_complete_when_coverage_rule():
    """Ingest SKILL.md Step 5 must document that complete_when conditions
    can be satisfied by ANY capability (required OR optional)."""
    for host in ("claude", "agents"):
        text = _read_skill_text(host)
        assert "complete_when coverage check" in text, (
            f"{host}/ingest/SKILL.md missing complete_when coverage check section"
        )
        assert "required OR optional" in text, (
            f"{host}/ingest/SKILL.md must state complete_when can use "
            f"evidence from required OR optional capabilities"
        )
        # The subtitle/ASR example must be present
        assert "subtitle.fetch" in text and "speech.transcribe" in text, (
            f"{host}/ingest/SKILL.md must include the video subtitle/ASR "
            f"fallback example in the complete_when coverage rule"
        )
