"""Host-independent wrapper: preserve binding even when subprocess shells change."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="", help="Current host Session ID; required for send/reply")
    parser.add_argument("command", choices=("snapshot", "thread", "show", "read", "send", "reply", "count", "wait"))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        binding = json.loads((Path(__file__).resolve().parents[1] / "binding.json").read_text(encoding="utf-8"))
        root = Path(binding["knowledge_base"])
        agent = binding["agent_id"]
        if not (root / "mail").is_dir() or not (root / "wiki").is_dir():
            parser.error("Bound knowledge base is unavailable; install a binding for this machine")
    except (OSError, ValueError, KeyError) as exc:
        parser.error(f"Mail is not bound; run oks mail setup: {exc}")
    for option in args.arguments:
        if option.split("=", 1)[0] in {"--path", "--agent", "--sender-kind", "--session-id"}:
            parser.error("Binding overrides are not allowed; use a separate binding or --session")
    if args.command in {"send", "reply"} and not args.session.strip():
        parser.error("send/reply require --session before the command")
    executable = shutil.which("oks")
    if not executable:
        parser.error("oks is not installed or not on PATH; install open-knowledge-studio")
    environment = dict(os.environ, OKS_ROOT=str(root), OKS_AGENT_ID=agent,
                       OKS_SESSION_ID=args.session, PYTHONIOENCODING="utf-8")
    command = [executable, "mail", args.command, *args.arguments]
    if args.command in {"send", "reply"}:
        command += ["--sender-kind", "agent", "--session-id", args.session]
    return subprocess.run(command, env=environment, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
