# v0.4.0 RC Acceptance Summary

**Branch**: `release/v0.4.0`
**Version**: `0.4.0.dev0` (package) / `v0.4.0-pre-rc-baseline` (tag)
**Date**: 2026-08-06

## RC Gate Status

```
[x] Wheel contains schemas, capabilities, providers, recipes, security
[x] Wheel contains skill templates (claude + agents, 10 skills each)
[x] oks skills-install --force materializes from wheel
[x] Wheel passes twine check
[x] pipx install from wheel works outside repo
[x] oks init builds correct instance
[x] capability catalog / doctor functional
[x] D1 static web validated
[x] D2 JS web validated (static→empty→honest partial)
[x] F2 PPTX validated (table extraction, chart placeholder, pptx-slide locator)
[x] F3 XLSX validated (sheet/range locators, formulas preserved not evaluated)
[x] Four natural language ingestions pass (Markdown, Scan PDF, Web, Video)
[ ] Cold start with fresh Agent session — requires separate Agent session
[x] partial user feedback clear (missing + reason + impact)
[x] result.json written for each ingestion
[x] 5 remote leak tests pass (headers, mapping, text, artifacts, E2E)
[ ] README single recommended path — pending user review
[x] CHANGELOG.md complete
[x] Full regression: 381 passed (92 cli/tests + 289 scripts/tests)
[x] No old-path references in runtime code
[x] Worktree clean (only .gitignore-tracked untrackable items remain)
[x] Per-scenario acceptance documents: 10 scenarios + security + artifacts-index
```

## Scenario Matrix

| # | Scenario | Bundle ID | Evidence | Status |
|---|----------|-----------|----------|--------|
| A | Markdown | `bundle:81a563e3` | 1 | complete |
| B | Text PDF | `bundle:244b7db5` | 33 | complete |
| C | Scan PDF+OCR | `bundle:2789f4ff` / `bundle:6700cc` | 46 OCR / 3 E2E | complete (OCR) / partial (E2E w/o OCR) |
| D1 | Static Web | `bundle:ff67a9d7` | 1 | complete |
| D2 | JS Web | fixture-based | 1 | partial (JS gap honest) |
| E | Video | `bundle:37e65159` / `bundle:9ae09d` | 9 full / 1 E2E | complete (subs) / partial (no login) |
| F1 | DOCX | scenario-f | 1 | complete |
| F2 | PPTX | `bundle:43e46e28` | 4 | partial (chart) |
| F3 | XLSX | fixture-based | 2 | partial (formulas) |
| G | AgentKey Live | `bundle:37c59b5a` | 1 | partial (encrypted) |

## Non-Blocking Gaps

- AgentKey WeChat content encrypted (API reachable, honest partial)
- Bilibili regular subtitles require login (danmaku + keyframes available)
- Fresh Agent session cold start not yet validated (needs separate session)
- Browser Provider blocked (Chrome Web Store)
- MinerU optional (~300MB dependency)
