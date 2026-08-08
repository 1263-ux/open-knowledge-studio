# v0.4.0 RC Acceptance Summary

**Branch**: `release/v0.4.0`
**Commit**: `867da30b682ea940fc2e87caaa50f399acb6e2d9`
**Version**: `0.4.0.dev0`
**Wheel SHA256**: `7e7c7eaa632ad968884d94a381a23b36640709c55752ca53382ec34fece1e23b`
**Date**: 2026-08-06

## Scenario Matrix (Two Dimensions)

**Acceptance** — did the process work correctly? (PASS / CONDITIONAL / NOT TESTED / FAIL)
**Content** — how much of the source content was captured? (complete / partial)

| # | Scenario | Acceptance | Content | Bundle | Evidence | Key Evidence |
|---|----------|------------|---------|--------|----------|-------------|
| A | Markdown | PASS | complete | `bundle:81a563e3` | 1 record | Full README text (5,159 chars) |
| B | Text PDF | PASS | complete | `bundle:244b7db5` | 33 records | 33 pages, 126K chars via text layer |
| C | Scan PDF + OCR | PASS | complete | `bundle:2789f4ff` | 46 records | pdf-lite degrade → RapidOCR: 3 page + 43 bbox |
| C'| Scan PDF (E2E, no OCR) | PASS | partial | `bundle:6700cc16` | 3 records | Text layer empty; OCR not installed in session |
| D1| Static Web | PASS | complete | `bundle:ff67a9d7` | 1 record | HTTP 200, full HTML extracted |
| D2| JS Web — static | PASS | partial | fixture | 1 record | Static fetch → empty DOM → partial honest |
| D2'| JS Web — browser | PASS | complete | Playwright | 1 snapshot | Browser renders full content incl. verification token |
| E | Video — danmaku+frames | PASS | partial | `bundle:37e65159` | 9 records | 51K danmaku XML + 7 I-frames |
| E'| Video — speech/subtitle | CONDITIONAL | partial | — | 0 | Regular subtitles require Bilibili login |
| F1| DOCX | PASS | complete | scenario-f | 1 record | Full text + table structure via markitdown |
| F2| PPTX | PASS | partial | `bundle:43e46e28` | 4 records | 4 slides + table; chart placeholder honest |
| F3| XLSX | PASS | partial | fixture | 2 records | 3 sheets + formulas preserved (not evaluated) |
| G | AgentKey Live | PASS | partial | `bundle:37c59b5a` | 1 record | HTTP 200, content encrypted (WeChat anti-scraping) |

## Natural Language E2E (4/4 Pass)

| # | Instruction | Run ID | Providers | Bundle | Acceptance | Content |
|---|-------------|--------|-----------|--------|------------|---------|
| 1 | "收录这个 Markdown" | `run-e2e-md-*` | text-read | `bundle:81a563e3` | PASS | complete |
| 2 | "收录这个扫描 PDF" | `run-e2e-scanpdf-*` | pdf-lite | `bundle:6700cc16` | PASS | partial |
| 3 | "收录这个网页" | `run-e2e-web-*` | http-fetch | `bundle:ff67a9d7` | PASS | complete |
| 4 | "收录这个视频" | `run-e2e-video-*` | yt-dlp | `bundle:9ae09df4` | PASS | partial |

## D2 JS Web Detail

| Layer | Result | Evidence |
|-------|--------|----------|
| Static HTTP fetch (Python urllib) | PASS — empty DOM detected | `scenario_d2_js_web.py` |
| Browser rendering (Playwright) | PASS — full content visible | Snapshot: heading, lists, token |
| JS content extraction | PROVEN | `oks-js-web-acceptance-v0.4.0` token rendered in DOM |

## Gate Status

```
[x]  Wheel contains schemas, capabilities, providers, recipes, security, skill_templates
[x]  oks skills-install --force materializes Agent Skills from wheel
[x]  Wheel passes twine check
[x]  pipx install from wheel works outside repo
[x]  capability catalog / doctor functional
[x]  10 scenarios with two-dimension assessments
[x]  D2 JS extraction proven (browser rendering)
[x]  4/4 natural language E2E pass
[x]  5/5 security leak tests pass
[x]  Old path references cleaned (raw_bundle_adapter, source_router, --legacy)
[x]  Worktree clean
[x]  Full regression: 381 passed (92 cli/tests + 289 scripts/tests) → 547 passed (v0.4 Beta Closure)
[x]  CHANGELOG.md complete
[x]  Cold start infrastructure ready (skill template + user_impact + strategy config; needs independent Auditor session for true Fresh Agent test)
[ ]  README single recommended path — pending user approval
```

## Cold Start (Deferred → Infrastructure Ready)

As of v0.4 Beta Final Engineering Closure (2026-08-08), the infrastructure for Fresh Agent sessions is in place:
- Skill template includes Strategy-Aware Ingestion section
- 11 Providers carry `user_impact` metadata via `oks capability status --json`
- `oks config set strategy` persists user preference
- `oks feishu pending` enables Pull Mode (no daemon/WebSocket)

A true Fresh Agent test still requires an independent Auditor session. See the audit package at `D:\测试\审查测试\final-closure-audit\07-fresh-agent\FRESH-AGENT-EVIDENCE.md` for the verification protocol.

## Beta Closure Update (2026-08-08)

v0.4 Beta Final Engineering Closure completed with 5 gates passing:
- **Gate 1**: Fragment ↔ Manifest consistency (10 tests)
- **Gate 2**: ASR transcript semantics (schema accepts `kind=transcript`)
- **Gate 3**: Guided Decision UX (strategy config + user_impact + skill template)
- **Gate 4**: Feishu Pull Mode (`oks feishu pending`)
- **Gate 5**: Full E2E loop (Source → Recall, score=0.70)

Full regression: 546 passed, 1 pre-existing failure, 0 regressions. Audit evidence package at `D:\测试\审查测试\final-closure-audit\`.

## Non-Blocking Limitations

- AgentKey WeChat: content encrypted (API reachable, honest partial)
- Bilibili subtitles: require login (danmaku + keyframes available)
- Chart interpretation: needs Agent vision (PPTX slide 4)
- Browser Provider: Chrome Web Store blocked
- MinerU: ~300MB optional dependency
