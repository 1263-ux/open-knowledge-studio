# Connect from a user's request

Interpret the requested assistant and knowledge space. Inspect `oks --version` and
the requested host's project instructions/configuration only when the Agent runs
outside the knowledge-base clone. The normal in-clone path needs no Skill install.
Claude-compatible projects conventionally use `.claude/skills`; generic Agent
projects use `.agents/skills`. Other hosts may use a different directory: verify it.
Do not claim every host loads a folder merely because you can write there.

Use the knowledge base explicitly identified by the user or the local Mail page's
connection guide. Verify its `mail/` and `wiki/` directories. If two unrelated KBs
are plausible, ask which space the user means; do not bind a personal space silently.

The normal path needs no Skill installation: `oks init` already materializes
`oks-mail`, and an Agent running inside that clone can call `oks mail inbox` or
`oks mail snapshot` directly. Choose a stable Agent ID (`claude`, `codex`, or a
team name) so the sender and recipient match.

Only when a host runs outside the KB should you use the optional portable binding
(inspect `oks mail setup --help` for the host's discovery directory):
`oks mail setup --agent <name> --path <kb> --skills-dir <host-skills-dir>`.
Quote paths correctly for the current shell. This creates machine-local
`binding.json`; it does not install another copy into an already initialized KB,
change host settings, or start a model process.

Validate with `oks mail snapshot` from the Agent's KB working directory. Report
“Mail built-in; mailbox readable” on success. Report “host must reload Skills” only
when the host is using an external portable binding, and verify the host loaded it
before saying that it did.
Only exercise send/reply when the user authorized actual communication; use that
Thread rather than inventing messages in the user's inbox.

If oks is missing, install the provided package in the user's intended environment.
If the host cannot run commands or discover Skills, explain the specific missing
capability; do not label it connected. No provider key or headless launcher is needed
for a native Agent which can invoke the CLI.

For another machine, use its local clone of the same KB. Git remote operations
follow the user's authorization. Never infer remote wake or background polling
from a successful local setup.
