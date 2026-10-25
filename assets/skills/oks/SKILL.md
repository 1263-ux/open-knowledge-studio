---
name: oks
description: Find reviewed Skills in the active OKS knowledge instance and load only the Skill needed for the current task. Use for knowledge retrieval, ingestion and reusable workflows without preloading every Skill.
---

# OKS entry

1. Confirm the intended instance with `oks status`; use `OKS_ROOT` when needed.
2. Search its reviewed Skill knowledge: `oks skills search "<task>" --limit 3`.
3. Select a relevant Skill and run its returned `load_command`, or
   `oks skills load <skill-id> --version <hit.skill_version>`. Bind the selected
   result to its exact reviewed version, especially across fine categories.
4. Read the returned instructions and use `assets_root` to resolve its bundled
   scripts, references and templates. Check dependencies before execution.
5. Execute only the steps needed for the user's authorized task. Loading does
   not run scripts, install dependencies, grant permissions or send messages.
6. For host discovery, use `oks skills load <skill-id> --version <hit.skill_version> --target agents` (or
   claude/qoder/codebuddy). The host may need a new session to discover it.
7. Remove an unchanged managed host copy with
   `oks skills unload <skill-id> --target agents` after use.

For new Skills, `oks skills import <folder> --type strategy --category <category>`
captures assets and prepares a draft. Skills occupy their own Wiki area, with
strategy/anti-pattern/concept and fine categories below those types. Review with
`oks drafts get <slug>` and promote only after explicit human approval using
`oks drafts promote <slug>`. An update is a new version requiring review; do not
copy the old review timestamp to it. Use `oks skills list` for pending candidates.

Do not invent a substitute when no reviewed Skill matches. Report the missing
prerequisite or prepare its review candidate. Keep ordinary knowledge under the
existing knowledge domains.
