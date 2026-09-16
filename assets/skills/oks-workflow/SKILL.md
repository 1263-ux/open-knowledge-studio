---
name: oks-workflow
description: Route OKS knowledge work through the smallest useful combination of recall, ingest, execution, trace, distillation, review, reuse, and durable collaboration. Use for multi-step learning, knowledge-compounding, or coordination tasks; do not run every Skill by default.
---

# OKS Workflow

Use this Skill as the Agent-facing router for the OKS knowledge-compounding workflow. OKS's primary product is knowledge learning, sedimentation, reuse, and compounding. Agent and Skills orchestrate work; OKS stores governed knowledge; Trace records execution provenance; Mail records only explicit durable collaboration facts.

## Route the smallest useful loop

1. Identify the user's goal, expected reusable result, and non-goals.
2. Recall existing knowledge before adding or repeating material.
3. Choose only the required Skill(s): `/ingest`, `/query`, `/compile`, `/promote`, `/archive`, `/media-ingest`, `/office`, `/oks-mail`, `/status`, or `/lint`.
4. Execute with the available Provider/Capability and preserve partial, failed, skipped, and environment-limited states.
5. Record Trace when the work has execution, review, or delivery value.
6. Record Mail only for explicit handoff, result, blocker, review/note, or knowledge-reference facts. Do not log ordinary chat.
7. Distill reusable knowledge or capability candidates only when repeated evidence and a clear review path exist.
8. Stop when the requested outcome and its acceptance evidence are satisfied.

## Route collaboration by intent

When the user wants to involve another team member, keep the interaction in the
current knowledge or execution context. Offer one of four intent-level actions:
request review, hand off work, report a result, or report a blocker. Resolve the
recipient from the stable profile and current scope when possible; do not ask the
user to assemble `@agent-id`, `thread_id`, or `session_id` unless the target is
ambiguous.

Use `/oks-mail` as the persistence helper after the intent is clear. Keep one
Thread across Session and Agent boundaries, and attach existing Evidence Refs
instead of copying knowledge text. A new Session reads the same Thread through
the host hook or an explicit `oks mail wait`/`snapshot` check and may reply to
that Thread.

This is durable asynchronous collaboration, not a live chat or execution call.
Do not claim that saving a record wakes, invokes, or completes the recipient.
High-frequency communication inside one Agent Session belongs to the host's
subagent/message mechanism and should not be written to Mail.

## Non-negotiable boundaries

- Raw material is not Wiki knowledge; never auto-promote.
- Trace is provenance, not a recallable memory bucket.
- Mail write/reply does not imply an Agent was woken, called, or completed work.
- A Session registry or Skill file does not prove an Agent is connected or online.
- Never expose a UI or claim a capability that lacks a real adapter or verification evidence.
- Do not create a new parallel state machine when an existing OKS artifact already expresses the fact.

For detailed routing, artifact contracts, and promotion rules, read the repository's `docs/skills/` pages when they are available.
