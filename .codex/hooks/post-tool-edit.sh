#!/usr/bin/env bash
# post-tool-edit.sh — PostToolUse wrapper.
# Passes stdin (editor JSON payload) through to the Python hook, drops stderr.
# Fails open (exit 0) so a tool is never blocked.
# OKS_PYTHON is baked in by `oks hook install` to point at the interpreter
# that can import knowledge_studio (pipx/venv safe); falls back to python3.
exec "${OKS_PYTHON:-C:/Users/chenfeng/AppData/Local/pipx/pipx/venvs/open-knowledge-studio/Scripts/python.exe}" "$(dirname "$0")/post-tool-edit.py" 2>/dev/null
