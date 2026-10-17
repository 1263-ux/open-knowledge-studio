---
title: Skills in Wiki
---

# Skills in Wiki

Skills occupy their own top-level area, separate from ordinary knowledge:

```text
wiki/skills/
├── strategies/<category>/
├── anti-patterns/<category>/
└── concepts/<category>/
```

Fine categories may be nested, such as `knowledge/retrieval` or
`development/java`. These are Skill knowledge types, not additional ordinary
knowledge domains. A Skill package can have cards in more than one type.
Full `SKILL.md`, scripts, references and templates are captured as a versioned
Raw snapshot. Wiki cards retain the reviewed package identity and hashes.

## Import and review

```sh
oks skills import /path/to/skill --type strategy --category knowledge/retrieval
oks skills import /path/to/skills --all --type strategy --category development
oks skills list --status draft
oks drafts get <draft-slug>
# Only after a human reviews the instructions and assets:
oks drafts promote <draft-slug>
```

Import preserves file bytes and produces Raw evidence and a draft. It does not
execute the Skill or approve it. Repeating the same import is idempotent;
an updated file creates a new version that requires review again. New versions
supersede the earlier reviewed card in the same type/category only when promoted.
The `oks` router itself is excluded from collection imports.

## Find and use one Skill

```sh
oks skills search "retrieve knowledge" --type strategy --category knowledge --limit 3
oks skills load query --version <version-from-search-hit>
```

Search returns compact previews of active, reviewed Skill cards using the native
OKS recall factors, including memory scores. `load` verifies all captured hashes,
returns the original instructions and materializes the assets in a versioned
instance-local cache. Resolve relative scripts, references and templates against
the returned `assets_root`; invoke their required interpreter explicitly.

Use the hit's `load_command` to bind loading to the exact reviewed version found
by search. Without `--version`, direct loading chooses the latest approved active
version of that Skill identifier across categories.

An Agent reads those instructions and performs the steps appropriate to the
authorized task. Loading does not execute scripts, install dependencies, grant
permissions or send messages. Wiki classification and commentary are searchable
knowledge; executable Skill instructions come from the reviewed Raw snapshot.
Changing those instructions means importing and reviewing a new package.

## Host discovery and removal

```sh
oks skills load query --version <version-from-search-hit> --target agents
oks skills unload query --target agents
```

Supported project-local hosts are `agents`, `claude`, `qoder`, and `codebuddy`.
The active host may need a new session to discover a newly installed Skill.
Existing same-name Skills are protected. Unload removes only copies previously
installed by this command and refuses modified files or added directories.

## Keep one small entry

```sh
oks skills install-router --target agents --compact
# Restore using the backup path returned above:
oks skills restore-router /path/to/instance/.oks/skill-backups/agents/<backup>
```

First import and review the required existing Skills. Then install the small
`oks` router. `--compact` moves unchanged bundled Skill copies into a recoverable
instance-local backup; custom copies and user edits remain installed. Restore
refuses to overwrite existing copies. Global agent directories are not touched.
The legacy `oks skills-install` command remains available for full installations.

Packages use portable relative paths, regular files, at most 1,024 files and
64 MiB of uncompressed content. Git metadata, dependency caches and virtual
environments are skipped and reported. Symlinks, junctions, traversal and path
collisions on case-insensitive hosts are rejected.
