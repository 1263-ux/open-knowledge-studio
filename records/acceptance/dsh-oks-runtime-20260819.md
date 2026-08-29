# dsh-oks runtime regression evidence

Date: 2026-08-19
Runtime: DSH Web profile web, http://127.0.0.1:3080, controlled acceptance process
Session: session-a4263541-e021-4ee1-9c61-6cc008b9cf8e

## AC1 / AC2 API

- POST /api/settings.describe returned result.ok=true.
- result.value.writable=true; result.value.hasDocument=true.
- namespaces count=12; oks namespace count=1.
- The oks namespace value resolved to 12 concrete fields, not null/unavailable.

## AC3 tools

The session request header contained the dsh-oks tool catalog. All six names were observed:

- oks_recall
- oks_status
- oks_wiki_use
- oks_metrics
- oks_inject_stats
- oks_inject_feedback

Real non-error calls:

- seq 329: oks_status -> non-error status report.
- seq 331: oks_recall -> non-error recall-response/v1-multi with knowledge and episodic hits.
- seq 333: oks_metrics -> non-error Knowledge Report Card.
- seq 1912: oks_inject_feedback -> non-error recorded injection rating.
- seq 2247: oks_inject_stats -> non-error JSON counters.
- seq 2249: oks_wiki_use slug=20260808-oks-e2e-audit-test-pipeline-verification -> non-error Recorded use, access_count=1.

## AC3 hooks

- seq 11 user/message contains <recalled-memory source="oks"> and inject_id=41a5a5f9.
- The pre-step hook therefore executed and injected OKS memory before the model turn.
- The first tool request header exposed the post-tool-capable injection feedback tool.
- The model then called oks_inject_feedback for the injected memory after tool execution; this is observable post-tool memory-signal behavior.
- This run is positive evidence for both pre-step injection and post-tool feedback/signal handling. It is not inferred from homepage HTTP 200.

## AC3 skill

- POST /api/skill.list with the dedicated sessionId returned result.ok=true.
- skill name oks-recall present; modelInvocable=true.

## AC4 runtime writeback

- Existing settings/recall.yaml was restored to recall.floor=0.7 after the reversible test.
- The controlled runtime cycle 0.70 -> 0.65 -> 0.70 was previously observed on the new 3080 runtime.
- settings.describe reflected 0.65 during the test and 0.70 after restoration.
- recall.yaml reflected the tested value and was restored; knowledge_base_path writeback to the user-level OKS config was also verified and restored.

## Boundaries

- AC2 GUI visual Owner confirmation is still pending; API evidence is not a substitute.
- Web logs must be checked for dsh-oks load errors; no such error was observed in the controlled runtime evidence.
- AC7 remains partial until human promotion and a real recalled Kimi-to-Ki3 output with before/after evidence exist.
- AC8 cloud publication, AC9 team signoff, AC10 external promotion, and AC11 fork/push/PR remain explicit pending/external states.


## Web log check

The controlled reload logs were checked at:

```text
<dsh-log-root>/controlled-reload/web-after.out.log
<dsh-log-root>/controlled-reload/web-after.err.log
```

The stderr file is empty, and no `dsh-oks`/plugin load error match was found in the available DSH logs. This is supplementary evidence; it does not replace the GUI Owner gate.

## Temporary comparison runtime cleanup

The comparison instance on port 3082 was verified by command line and stopped after its evidence was saved. The controlled acceptance runtime on port 3080 was left running for Owner GUI confirmation.
