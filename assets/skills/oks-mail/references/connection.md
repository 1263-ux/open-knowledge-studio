# Connect from a user's request

Interpret the requested assistant and knowledge space. Inspect `oks --version`,
`oks mail setup --help`, and the requested host's project instructions/configuration
to find its actual Skill discovery directory. Prefer a project-local install.
Claude-compatible projects conventionally use `.claude/skills`; generic Agent
projects use `.agents/skills`. Other hosts may use a different directory: verify it.
Do not claim every host loads a folder merely because you can write there.

Use the knowledge base explicitly identified by the user or the local Mail page's
connection guide. Verify its `mail/` and `wiki/` directories. If two unrelated KBs
are plausible, ask which space the user means; do not bind a personal space silently.

Choose a stable named Agent (for example `reviewer` or the requested assistant name).
Use `oks mail setup --agent <name> --path <kb> --skills-dir <host-skills-dir>`.
Quote paths correctly for the current shell. This installs only oks-mail; it does
not change the host's global settings or start a model process. Existing differing
files cause a stop; inspect them before proposing replacement.

Validate through the installed helper's `snapshot` command from another working
directory. Report “Skill installed; mailbox readable” on success. Report “host must
reload Skills” if necessary, and verify the host loaded it before saying that it did.
Only exercise send/reply when the user authorized actual communication; use that
Thread rather than inventing messages in the user's inbox.

If oks is missing, install the provided package in the user's intended environment.
If the host cannot run commands or discover Skills, explain the specific missing
capability; do not label it connected. No provider key or headless launcher is needed
for a native Agent which can invoke the CLI.

For another machine, use its local clone of the same KB and install a local binding.
Git remote operations follow the user's authorization. Never infer remote wake,
automatic Git sync or background polling from a successful local installation.


