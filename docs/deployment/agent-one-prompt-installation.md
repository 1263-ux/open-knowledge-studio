# Agent One-Prompt OKS Operation

Date: 2026-07-29

Use this prompt when asking a new Agent to validate or operate OKS from a clean
environment. It is intentionally narrow: prove the core lifecycle before
testing heavy extractors or Feishu.

## One-Prompt

```text
You are validating Open Knowledge Studio as an Agent-operated knowledge loop.

Goal:
Run one complete, traceable OKS learning loop on a public text source:
Source -> Raw Bundle -> Candidate -> explicit human review -> Wiki -> search/recall -> grounded answer -> evaluation.

Rules:
1. Use an isolated temporary OKS root. Do not modify an existing personal or production knowledge base.
2. Install only the minimum required dependencies for the selected source. Do not install PDF, formula, video, OCR, ASR, Feishu, browser, or cloud components unless the task explicitly asks for that capability.
3. Preserve evidence: source URL or file path, content hash, command, exit code, elapsed time, Raw Bundle path, Candidate path, Wiki path, and search/recall/lint output.
4. Do not promote a Candidate to Wiki until the human explicitly approves it, for example by replying "accept" or an equivalent unambiguous approval in the user's language.
5. Keep extraction, Agent interpretation, human review, Wiki promotion, recall, and final answer as separate states.
6. Mark every assertion as passed, failed, partial, skipped, awaiting_human, or environment_limited. Do not convert a partial run into "basically passed".
7. When producing the final answer, cite the locator supplied by the Wiki or Recall context for each factual claim.

Suggested source:
- Public-domain text or markdown.
- Avoid anti-bot platforms for the first validation.

Required commands:
- oks --version
- oks init <isolated-root>
- oks ingest <source> --output <isolated-root>
- oks drafts list
- oks drafts promote <slug> only after human approval
- oks search "<query>"
- oks recall "<query>"
- oks lint

Deliverables:
1. A short report containing environment, versions, commands, exit codes, paths, hashes, and state classification.
2. The generated Candidate before review.
3. The promoted Wiki path after review.
4. A final grounded answer using recalled evidence and explicit locators.
5. A list of product failures and environment limitations discovered during the run.
```

## Operator Notes

For the first validation, choose the lightest source that proves the lifecycle.
Do not start with video, formula OCR, or Feishu. Those are component tests, not
the core proof.

After the text loop passes, test optional capabilities one at a time in isolated
environments:

| Capability | Purpose | Stop condition |
|---|---|---|
| document | Office, HTML, text extraction | Raw validates and can reach Candidate |
| pdf | PDF layout extraction | Missing binary or model is recorded honestly |
| formula | formula-specific value over PDF/image | CLI must expose the capability directly |
| watch | video/audio extraction | missing `ffprobe` or platform anti-bot is environment/platform friction |
| Feishu | optional capture/review control plane | never required for non-Feishu CLI success |

Feishu-specific work must use runtime credentials only and a dedicated test
Base. It must not touch a business Base, persist secrets, or be treated as a
precondition for the CLI learning loop.
