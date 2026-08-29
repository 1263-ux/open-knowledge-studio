# Anthropic DOCX Adapter

This is a runtime integration contract, not a vendored copy of Anthropic's
skill. If the active host independently provides the upstream `docx` skill,
invoke it directly for create/edit/review work and keep OKS responsible for
evidence selection, source ledger, and final QA.

Probe: the host exposes the `docx` skill. If absent, route to the host
`documents` workflow. Do not install, copy, or
redistribute proprietary upstream instructions as part of OKS.
