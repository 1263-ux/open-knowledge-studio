# Changelog

## v0.4.0 (Unreleased)

### Agent-Native Ingestion Architecture

- **Breaking**: Legacy extractor path removed. `--legacy` flag, `OKS_ENABLE_LEGACY_PROVIDERS`
  env var, `raw_bundle_adapter.py`, `source_router.py`, and old extractors
  (`extractors/watch.py`, `markitdown.py`, `mineru.py`, `image.py`, `web.py`)
  are permanently deleted. Git tag `v0.4.0-legacy-final` preserves the old code.
- New capability system: 18 stable actions in `capabilities/actions.yaml`
- 16 Provider directories with `provider.yaml` + `SKILL.md`
- 7 ingestion Recipes: text, pdf, office, image, web, audio, video
- 3 new protocols: SourceEnvelope, EvidenceFragment, EvidenceManifest
- `oks raw-commit` validates and atomically writes evidence bundles
- `/ingest` Skill: Agent-native orchestration (Source → Provider → Fragment → Manifest → raw-commit)

### Packaging

- Runtime assets (`schemas/`, `providers/`, `capabilities/`, `recipes/`, `security/`)
  are now shipped inside the Wheel package
- Resources accessed via `importlib.resources.files()` — no repo-relative path guessing
- Wheel install verified with `pipx` outside the source directory

### CLI

- `oks capability catalog` — user-friendly capability→provider mapping
- `oks capability doctor` — environment diagnostic (Built-in/Local/Remote/Manual groups)
- `--json` and `--verbose` flags on capability commands for Agent consumption
- `oks ingest` in pure terminal outputs `Agent Required` notice — no phantom Agent invocation
- `oks skills-install` — materialize Agent skill templates from installed package

### Security

- Unified `knowledge_studio/security/` redaction module
- Covers: 9 HTTP header types, 24 JSON keys, 7 free-text patterns (Bearer, JWT, Basic, AWS)
- 5/5 leak tests pass (headers, mapping, text, artifacts, E2E)

### Acceptance

- 10 real scenarios verified: Markdown, Text PDF, Scanned PDF+OCR, Static Web, JS Web,
  Video+Subtitles+Keyframes, DOCX, PPTX, XLSX, AgentKey live API call
- Negative tests: MISSING_ARTIFACT, ARTIFACT_HASH_MISMATCH, INCOMPLETE_LOCATOR,
  ORPHAN_EVIDENCE, credential leak — all correctly rejected

### Fixed

- `oks ingest --legacy` now correctly errors with "No such option" (exit 2)
- Test count stabilized at 92 after legacy module deletion
- Dead `_connector_available`/`_connector_command` stubs removed from CLI
- `capability_check` import now uses `oks_connector` package path
- Windows encoding fixes (UTF-8 write_text, colon-free run IDs)

---

## v0.3.0

- Base knowledge engineering CLI with search, recall, wiki CRUD, drafts, lint, metrics
- 6+1-factor recall engine with decay system
- Date-based raw/ organization
- Feishu worker integration (Source + Review planes)
- Global config (`~/.oks/config.json`)
