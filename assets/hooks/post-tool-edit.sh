#!/usr/bin/env bash
# post-tool-edit.sh — PostToolUse wrapper.
# Passes stdin (editor JSON payload) through to the Python hook. stderr is
# captured and dropped on success, and surfaced on a non-zero exit — discarding
# it made a crashed engine indistinguishable from "no conflict found". Always
# exits 0 so a tool is never blocked.
# OKS_PYTHON is baked in by `oks hook install` to point at the interpreter
# that can import knowledge_studio (pipx/venv safe); falls back to python3.
engine="$(dirname "$0")/post-tool-edit.py"
errlog="$(mktemp -t oks-hook-posttool.XXXXXX 2>/dev/null)"
if [ -z "$errlog" ]; then
    "${OKS_PYTHON:-python3}" "$engine" 2>/dev/null
    exit 0
fi
trap 'rm -f "$errlog"' EXIT
"${OKS_PYTHON:-python3}" "$engine" 2>"$errlog"
status=$?
if [ "$status" -ne 0 ]; then
    printf 'oks hook: post-tool engine exited %s — run `oks hook install` to refresh it\n' "$status" >&2
    tail -n 5 "$errlog" >&2
fi
exit 0
