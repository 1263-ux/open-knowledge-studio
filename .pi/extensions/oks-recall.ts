/**
 * oks-recall — pi extension for OKS auto-recall injection.
 *
 * Subscribes to `before_agent_start` (fires after user submits a prompt,
 * before the agent loop). Runs the same hook used by Claude Code. The Python
 * hook owns knowledge filtering and cooldown, but Mail is checked even for a
 * short prompt such as "继续", so Pi and Claude have the same delivery rule.
 *
 * Prerequisite: `oks hook install` must have been run in this project
 * (so `.claude/hooks/user-prompt-recall.py` exists). The script resolves
 * the KB root via OKS_ROOT → ~/.oks/config.json → cwd, so a dev repo
 * with an empty wiki/ still injects memory from the configured KB.
 *
 * Tunables (same env as the Claude Code hook):
 *   OKS_RECALL_MINLEN    skip prompts shorter than this (default 6)
 *   OKS_RECALL_FLOOR     min relevance to inject (default 0.7, in the .py)
 *   OKS_RECALL_TOPN      max memories injected (default 3, in the .py)
 *   OKS_RECALL_COOLDOWN  turns before re-injecting same slug (default 10)
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

function kbRoot(): string | null {
  const env = process.env.OKS_ROOT?.trim();
  if (env && existsSync(join(env, "wiki"))) return env;
  try {
    const configPath = join(homedir(), ".oks", "config.json");
    if (existsSync(configPath)) {
      const config = JSON.parse(readFileSync(configPath, "utf-8")) as {
        knowledge_base_path?: string;
      };
      const configured = config.knowledge_base_path?.trim();
      if (configured && existsSync(join(configured, "wiki"))) return configured;
    }
  } catch {
    // Fall through to the current directory; this extension is fail-open.
  }
  const cwd = process.cwd();
  return existsSync(join(cwd, "wiki")) ? cwd : null;
}

function hookPython(script: string): string {
  const configured = process.env.OKS_PYTHON?.trim();
  if (configured) return configured;

  // `oks hook install` bakes the importable interpreter into the Bash
  // wrapper. Reuse that value so Pi works on Windows even when `python3` is
  // not on PATH, without duplicating the pipx/venv discovery logic here.
  const wrapper = script.replace(/user-prompt-recall\.py$/, "user-prompt-recall.sh");
  try {
    const text = readFileSync(wrapper, "utf-8");
    const match = text.match(/\$\{OKS_PYTHON:-([^}]+)\}/);
    if (match?.[1]) return match[1].trim().replace(/^['"]|['"]$/g, "");
  } catch {
    // Use the platform default below.
  }
  return process.platform === "win32" ? "python" : "python3";
}

export default function (pi: ExtensionAPI) {
  pi.on("before_agent_start", async (event, ctx) => {
    const prompt = (event.prompt ?? "").trim();
    const root = kbRoot();
    if (!root) return;

    // Locate the OKS hook script (installed by `oks hook install`) from the
    // resolved KB root, matching the PostToolUse extension and Claude hook.
    const script = join(root, ".claude/hooks/user-prompt-recall.py");
    if (!existsSync(script)) return; // oks hook not installed — skip silently

    // Session id drives cooldown state (per-session dedup).
    const ctxAny = ctx as unknown as {
      sessionManager?: { getSessionId?: () => string };
    };
    const sessionId =
      ctxAny.sessionManager?.getSessionId?.() ?? "pi-default";

    const payload = JSON.stringify({
      prompt,
      session_id: sessionId,
      cwd: process.cwd(),
      agent_id: process.env.OKS_AGENT_ID ?? "pi",
    });

    try {
      const out = execFileSync(hookPython(script), [script], {
        input: payload,
        timeout: 10000,
        encoding: "utf-8",
        env: {
          ...process.env,
          OKS_ROOT: root,
          OKS_AGENT_ID: process.env.OKS_AGENT_ID ?? "pi",
        },
      });
      const content = (out ?? "").trim();
      if (!content) return; // nothing relevant above floor — inject nothing
      return {
        message: {
          customType: "oks-recall",
          content,
          display: true, // show injected memory in the UI (transparent); set false once stable
        },
      };
    } catch {
      return; // fail open — never block a prompt on recall failure
    }
  });
}
