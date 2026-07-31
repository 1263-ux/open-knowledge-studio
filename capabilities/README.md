# Capability Registry

Each JSON file is validated against `schemas/capability-manifest.schema.json` and describes one installed integration boundary. Studio routing reads these manifests; it must not infer available tools from a prompt.

Versions in this directory describe the OKS integration contract. The exact executable/package/model version used by an individual run belongs in `Processing Run.job.version` and the Raw Bundle provenance agent.
