# Book POC A/B Evaluation Protocol

- Frozen: 2026-07-29
- Status: `frozen_before_human_promotion`
- Purpose: test whether a human-reviewed OKS Wiki and its Recall context improve
  a model's answers over the same model without OKS context.

## Experimental control

The earlier A-group result (`1/6` fully correct) is valid exploratory evidence,
but its exact generation options were not retained. It therefore cannot be the
sole final causal baseline. The final comparison reruns A and B with one frozen
request:

| Setting | Value |
|---|---|
| Runtime | local Ollama |
| Model | `gpt-oss:20b` |
| Local model ID observed before the run | `17052f91a42e` |
| Temperature | `0` |
| Seed | `20260729` |
| Top-p | `1` |
| Maximum generated tokens | `2048` |
| Streaming | disabled |
| Tools and external network | unavailable |

Both groups receive the same system and user instructions. The only independent
variable is the `<context>` block:

- A: `NO OKS CONTEXT PROVIDED`.
- B: the exact human-approved Wiki page returned through the post-promotion
  knowledge path. Raw files are not added directly.

The B context and its SHA-256 must be preserved. If the model/runtime or any
generation option differs, the run is not comparable and must be repeated.

## Questions

1. What were the responsibilities and approximate sizes of de Prony's three
   sections?
2. Why were two workshops used, and what assurance did that provide?
3. What surprising accuracy observation did Babbage make about the third
   section?
4. Which section did Babbage expect a calculating engine to replace, and what
   work would remain for analysts?
5. Which three initial values are sufficient in the square-number difference
   example, and why?
6. What two conditions does the chapter give for extensive division of labour?

## Frozen answer key

1. First section: five or six eminent mathematicians selected expressions
   suitable for simple numerical work by many people and did little or no
   numerical calculation. Second: seven or eight mathematically capable people
   converted formulas into numbers, distributed/received work, and verified
   results. Third: sixty to eighty people used only addition and subtraction to
   produce the completed tables. Evidence: section 244, source lines 5904-5938.
2. Two separate workshops performed the same calculations for reciprocal
   verification. The source supports independent cross-checking, not continuity
   after machinery or staffing failure. Evidence: section 243, lines 5872-5902.
3. Nine-tenths knew no arithmetic beyond addition and subtraction and were
   usually more accurate than people with broader arithmetic knowledge.
   Evidence: section 244, lines 5930-5938.
4. The calculating engine would replace the whole third section. Analysts would
   focus on simplifying how analytical formulas are converted into numbers.
   Evidence: section 245, lines 5940-5956.
5. `1` (first table value), `3` (first first-difference), and `2` (constant
   second difference). Repeatedly adding `2` generates the first differences;
   adding those generates subsequent squares. Evidence: section 248, lines
   5992-6035.
6. There must be great demand for the output and large capital available.
   Evidence: section 251, lines 6081-6084.

## Per-question scoring

Each question receives:

- `1.0`: all required facts are correct; no material unsupported detail.
- `0.5`: the central answer is correct but incomplete, imprecise, or mixed with
  a minor unsupported detail.
- `0.0`: central answer is wrong, missing, contradicted, or dominated by
  unsupported claims.

Additional metrics:

- **Coverage:** number of required fact units present divided by total units.
- **Source fidelity:** count every factual statement not supported by the
  approved Wiki/context; inferred advice must be labelled.
- **Traceability:** one point per answer that identifies the supporting section
  and locator available in the supplied context.
- **Hallucination:** count fabricated quotations, numbers, responsibilities,
  causal mechanisms, or source claims.
- **Usefulness:** `0-2` for whether the final synthesis can guide a modern
  workflow without presenting historical analogy as empirical proof.

Scoring is performed against this answer key after both outputs exist. The
answer key must not be edited after seeing B.

## Success threshold

B demonstrates measurable value only if all are true:

1. total correctness improves by at least `2.0/6` over the frozen A rerun;
2. B has no fabricated quotation and no more unsupported factual claims than
   A; if A has zero unsupported claims, B must also have zero;
3. at least `5/6` B answers are traceable to the supplied Wiki context;
4. B does not turn the two `[inferred]` engineering lessons into claims made
   explicitly by Babbage.

If B misses the threshold, the POC is not passed. Diagnose Candidate granularity,
Wiki promotion shape, query terms, Recall ranking, and context injection before
adding more extractors or architecture.

## Pre-promotion negative control

Before human approval:

- `oks search "de Prony division of mental labour"` returned no Wiki result
  with exit code `0`.
- `oks recall "What were the three sections in de Prony division of mental
  labour?"` returned Episodic Raw matches with exit code `0`.

This distinction matters: a successful dual-path `recall` before promotion does
not prove the reviewed-Wiki lifecycle is complete. The final B input therefore
uses the post-promotion Knowledge page, while the full `search` and `recall`
commands are still run and recorded as lifecycle checks.

## Frozen A result

The reproducible A request completed before human promotion:

| Field | Result |
|---|---|
| Model ID | `17052f91a42e` |
| Model size | `13 GB` |
| Prompt SHA-256 | `12a38860d74342d8613cc90982dc03f5c131f9d61d97a259616cde078956a9af` |
| Response SHA-256 | `87d2d4a2f121417b2b87e7474826e5e5ff7be001e14c25de428587ff5bddacd2` |
| Artifact SHA-256 | `ecdb9fb9ab92cdadf4c8c5471678778a2672abb8eb5efcfd20865aa9b50e44ff` |
| Response | “I’m sorry, but I don’t have enough information to answer these questions accurately.” |
| Correctness | `0/6` |
| Required-fact coverage | `0%` |
| Unsupported factual claims | `0` |
| Traceable answers | `0/6` |

This is a different failure mode from the exploratory A run: the exploratory
run hallucinated, while the frozen run abstained. The final comparison uses the
frozen run because its exact prompt, options, model identity, timing, response,
and hashes are preserved.

## Execution artifacts

The repeatable local runner is intentionally kept under ignored
`.codex-tmp/book-poc/`; it is experimental evidence, not a new OKS subsystem.
It must write the prompt, options, model identity, timestamps, response, timing,
and hashes for both groups.
