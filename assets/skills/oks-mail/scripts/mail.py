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
    binding_path = Path(__file__).resolve().parents[1] / "binding.json"
    try:
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
        root = Path(binding["knowledge_base"])
        agent = binding["agent_id"]
    except (OSError, ValueError, KeyError):
        # ``oks init`` already ships this Skill.  A binding is only needed for
        # a portable Skill copied outside the KB; inside a KB infer the root
        # and host identity exactly as the native ``oks mail`` command does.
        candidates = []
        if os.environ.get("OKS_ROOT", "").strip():
            candidates.append(Path(os.environ["OKS_ROOT"]))
        candidates.extend([Path.cwd(), *Path.cwd().parents])
        root = next((candidate.expanduser().resolve() for candidate in candidates
                     if (candidate / "mail").is_dir() and (candidate / "wiki").is_dir()), None)
        if root is None:
            parser.error("找不到 OKS 知识库；请从包含 mail/ 和 wiki/ 的目录运行，或设置 OKS_ROOT")
        agent = os.environ.get("OKS_AGENT_ID", "").strip()
        if not agent and (os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("CLAUDECODE")):
            agent = "claude"
        if not agent and (os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_CLI")):
            agent = "codex"
        if not agent:
            parser.error("无法判断 Agent 身份；设置 OKS_AGENT_ID 后重试")
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
