/**
 * oks-recall — pi extension for OKS auto-recall injection.
 *
 * Subscribes to `before_agent_start` (fires after user submits a prompt,
 * before the agent loop). Runs the OKS recall engine via the bundled
 * `.claude/hooks/user-prompt-recall.py` script (which already implements
 * floor filtering, cooldown dedup, trivial-prompt skip, and fail-open),
 * and injects the `<recalled-memory>` block as a persistent message so
 * the LLM sees relevant wiki memory alongside the user's prompt.
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
import { existsSync } from "node:fs";
import { join } from "node:path";

const MINLEN = parseInt(process.env.OKS_RECALL_MINLEN ?? "6", 10);

const TRIVIAL = new Set([
  "你好", "谢谢", "多谢", "ok", "okay", "好", "好的", "嗯", "行", "继续",
  "hi", "hello", "thanks", "thx", "yes", "no", "是", "对", "收到",
]);

export default function (pi: ExtensionAPI) {
  pi.on("before_agent_start", async (event, ctx) => {
    const prompt = (event.prompt ?? "").trim();
    if (!prompt || prompt.length < MINLEN || TRIVIAL.has(prompt.toLowerCase())) {
      return;
    }

    // Locate the OKS hook script (installed by `oks hook install`).
    const script = join(process.cwd(), ".claude/hooks/user-prompt-recall.py");
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
      agent_id: process.env.OKS_AGENT_ID ?? "",
    });

    try {
      const out = execFileSync("python3", [script], {
        input: payload,
        timeout: 10000,
        encoding: "utf-8",
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
