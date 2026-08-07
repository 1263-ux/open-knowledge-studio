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
