#!/usr/bin/env bash
# user-prompt-recall.sh — UserPromptSubmit wrapper.
# Passes the original stdin (editor JSON payload) through to the Python hook.
# jieba writes chatter to stderr, so stderr is captured and dropped on success
# to keep stdout a clean <recalled-memory> block. On a non-zero exit it is
# surfaced instead — discarding it made a crashed engine indistinguishable from
# "no memory matched". Always exits 0 so a prompt is never blocked.
# OKS_PYTHON is baked in by `oks hook install` to point at the interpreter
# that can import knowledge_studio (pipx/venv safe); falls back to python3.
engine="$(dirname "$0")/user-prompt-recall.py"
errlog="$(mktemp -t oks-hook-recall.XXXXXX 2>/dev/null)"
if [ -z "$errlog" ]; then
    "${OKS_PYTHON:-python3}" "$engine" 2>/dev/null
    exit 0
fi
trap 'rm -f "$errlog"' EXIT
"${OKS_PYTHON:-python3}" "$engine" 2>"$errlog"
status=$?
if [ "$status" -ne 0 ]; then
    printf 'oks hook: recall engine exited %s — run `oks hook install` to refresh it\n' "$status" >&2
    tail -n 5 "$errlog" >&2
fi
exit 0
