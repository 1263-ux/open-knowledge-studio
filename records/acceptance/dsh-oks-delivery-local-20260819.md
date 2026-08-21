# dsh-oks local delivery inventory

Date: 2026-08-19
Status: local evidence inventory; does not substitute for Owner GUI/human review or remote delivery.

## AC7-AC11 artifact inventory

| AC | Artifact | Exists | Classification |
|---|---|---:|---|
| AC7 | case Markdown (..\dsh-oks\docs\cases\kimi-k3-to-ki3.md) | 1 | real source/run + draft; case incomplete |
| AC7 | real run record (..\dsh-oks\docs\cases\kimi-k3-to-ki3-run-20260819.md) | 1 | real source/run + draft; case incomplete |
| AC7 | raw bundle (raw\2026\08\08\agent-capture\bundle-b70c3666e8347e6f) | 1 | real source/run + draft; case incomplete |
| AC7 | Kimi draft (drafts\kimi-k3-review-bilibili.md) | 1 | real source/run + draft; case incomplete |
| AC8 | SKILL.md (..\dsh-oks\skills\oks-case-init\SKILL.md) | 1 | local draft; cloud pending |
| AC9 | team ingestion guide (..\dsh-oks\docs\team-ingestion-guide.md) | 1 | local guide; team signoff pending |
| AC10 | Codex install prompt (..\dsh-oks\docs\delivery\codex-install-prompt.md) | 1 | local material; external publication pending |
| AC10 | README install and usage (..\dsh-oks\README.md) | 1 | local material; external publication pending |
| AC10 | promotion material (..\dsh-oks\docs\delivery\promotion-material.md) | 1 | local material; external publication pending |
| AC10 | rc.6 compatibility note (..\dsh-oks\docs\windows-rc6-install.md) | 1 | local material; external publication pending |
| AC11 | PR draft (..\dsh-oks\docs\delivery\pr-draft.md) | 1 | local PR draft; remote action pending |

## AC7 evidence boundary

- Real execution: source URL, raw bundle, provider chain (`yt-dlp -> ffmpeg -> faster-whisper`), `oks status`, `oks config show`, and non-error `oks recall --format json` are recorded.
- Not completed: human approval/promotion into `wiki/`, recall hit from the promoted page, final Ki3 plan, and screenshots/recording.
- Therefore AC7 remains `PARTIAL`, not PASS.

## AC8-AC11 boundary

- AC8: local `oks-case-init` Skill draft includes inputs, initialization procedure, output structure, and guardrails; cloud publication was not performed.
- AC9: team guide covers GitHub, articles, AI Native, Agent content, directory organization, recall, and feedback; team acceptance is not recorded.
- AC10: install prompt includes the authoritative raw GitHub SKILL URL; README, case, promotion, and rc.6 notes are local; external publication was not performed.
- AC11: source/build/docs/PR draft are local and uncommitted; fork, push, PR, release, deployment, and publish were not performed.

## Required next actions

1. Owner visually accepts the Web OKS settings card.
2. Owner reviews/approves the Kimi draft, then the executor promotes through the normal OKS flow.
3. After promotion, rerun recall, save the Ki3 output, and capture before/after evidence.
4. Authorize each external repository action separately before fork/push/PR/release/publication.
