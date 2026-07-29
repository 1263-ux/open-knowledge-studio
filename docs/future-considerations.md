# Future Considerations

Date: 2026-07-29

These items are intentionally outside the current landing cycle because they are
not required to prove the first OKS knowledge loop.

## Not Current Scope

- Distributed Worker coordination.
- Redis, message queues, microservices, or Kubernetes.
- Multi-machine lease protocols.
- A new plugin marketplace.
- A new Skill Hub.
- A new Agent framework or universal tool protocol.
- Broad extractor registry abstractions beyond the existing capability install
  surface.
- Treating Feishu as mandatory infrastructure.

## Later Product Work

- Make final-answer traceability a deterministic post-processing check, not
  only a prompt instruction.
- Improve plain-text Raw locator granularity from document-level evidence to
  paragraph or line ranges.
- Fix mojibake in generated warnings and local model outputs.
- Revisit heavy extractors one at a time after the clean text loop stays
  reproducible.
- Consider remote OCR/ASR/document parsing APIs where they reduce install
  weight without losing provenance or violating platform terms.
- Add containerized optional-capability runners if local dependency isolation
  remains painful.

Each item should start with evidence from a failed or high-friction acceptance
run. Do not implement these because an architecture diagram looks incomplete.
