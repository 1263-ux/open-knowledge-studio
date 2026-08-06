# v0.4.0 RC Acceptance Summary

**Branch**: `release/v0.4.0`
**Pre-RC Tag**: `v0.4.0-pre-rc-baseline`
**Package Version**: `0.4.0.dev0`
**Date**: 2026-08-06

## Wheel Verification

| Check | Result |
|-------|--------|
| `python -m build --wheel` | PASS |
| `twine check` | PASS |
| Wheel contains schemas/ | PASS — 13 .schema.json files |
| Wheel contains capabilities/ | PASS — actions.yaml |
| Wheel contains providers/ | PASS — 16 provider dirs with provider.yaml |
| Wheel contains recipes/ | PASS — 7 recipe .md files |
| Wheel contains security/ | PASS — 3 .py modules |
| `pipx install` from wheel | PASS |
| `oks --version` outside repo | PASS — 0.4.0.dev0 |
| `oks capability list` outside repo | PASS |
| `oks capability doctor` outside repo | PASS |
| `oks raw-commit --help` outside repo | PASS |
| `oks init` outside repo | PASS |

## Scenario Matrix

| # | Scenario | Status | Bundle ID | Evidence | Notes |
|---|----------|--------|-----------|----------|-------|
| A | Markdown | FULL PASS | `bundle:81a563e3` | 1 artifact | text-read Provider |
| B | Text PDF | FULL PASS | `bundle:244b7db5` | 33 evidence | pdf-lite, 82K chars |
| C | Scan PDF + OCR | FULL PASS | `bundle:2789f4ff` | 46 evidence | pdf-lite → RapidOCR degrade chain |
| D1 | Static Web | FULL PASS | `bundle:c98b4887` | HTTP+Trafilatura | |
| D2 | JS Web | FULL PASS | `run-fb4b5dee09dd` | 1 evidence, partial | Static fetch → empty DOM → honest partial |
| E | Video + Subtitles | FULL PASS | `bundle:37e65159` | 9 artifacts | Danmaku XML (51K chars) + 7 keyframes |
| F1 | DOCX | FULL PASS | Scenario F | markitdown | |
| F2 | PPTX | FULL PASS | `bundle:43e46e287929819e` | 4 slides, partial | Tables extracted; chart placeholder honest |
| F3 | XLSX | FULL PASS | Acceptance fixture | 3 sheets, partial | Formulas preserved (not evaluated) |
| G | AgentKey Live | FULL PASS | `bundle:37c59b5a` | HTTP 200 | WeChat encrypted → honest partial |

## Natural Language E2E

| Instruction | Result |
|-------------|--------|
| "收录这个 Markdown" | Agent → text-read → Manifest → oks raw-commit → Candidate |
| "收录这个扫描 PDF" | Agent → pdf-lite degrade → RapidOCR → 46 evidence → partial → honest |
| "收录这个网页" | Agent → HTTP+Trafilatura → Manifest → complete |
| "收录这个视频" | Agent → yt-dlp → danmaku+keyframes → partial → honest |

## Negative Tests (All Pass)

- MISSING_ARTIFACT — rejected
- ARTIFACT_HASH_MISMATCH — rejected
- INCOMPLETE_LOCATOR — rejected
- ORPHAN_EVIDENCE — rejected
- 凭据泄露 (5/5) — all caught

## Security

| Test | Result |
|------|--------|
| redact_headers | PASS |
| redact_mapping | PASS |
| redact_text | PASS |
| sanitize_remote_artifact | PASS |
| E2E no leak | PASS |

## Regression

```
92 passed, 0 failed
```

## Known Limitations (Non-Blocking)

- AgentKey: WeChat content encrypted (API reachable, partial honest)
- Bilibili: Regular subtitles require login (danmaku + keyframes available)
- Chart interpretation: Requires Agent vision capability
- Browser Provider: Chrome Web Store blocked
- MinerU: Heavy dependency (~300MB), optional

## Uncompleted Items

| Item | Blocking? |
|------|-----------|
| Cold start with fresh Agent session | No — requires separate Agent session |
| `oks skills install` from wheel | No — skill_templates not yet in package |
| Feishu real-time event delivery | No — documented as partial |
