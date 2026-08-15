/**
 * Deep links that open a coding agent with a Planlog prompt pre-filled.
 *
 * Every scheme here only *pre-fills* the agent's input — none of them submit. Keep it that
 * way: the prompt embeds a user-controlled plan title, and "a human reads it before pressing
 * Enter" is the entire reason that is safe.
 *
 * Pure and dependency-free (no React, no `window`) so it is SSR-safe and can be exercised
 * with plain node.
 */

export type AgentLinkKind = "deeplink" | "web" | "copy";

export type AgentLinkId =
  | "cursor"
  | "claude-code"
  | "claude-vscode"
  | "cursor-web"
  | "copy";

export type AgentLink = {
  id: AgentLinkId;
  label: string;
  kind: AgentLinkKind;
  /** Absent for `kind: "copy"`, and for links dropped over their length cap. */
  href?: string;
  hint?: string;
  disabled?: boolean;
  /** Why it is disabled — rendered under the label. */
  reason?: string;
};

/** Claude Code caps `q` at 5,000 characters (decoded). */
export const CLAUDE_PROMPT_MAX = 5000;
/** Cursor caps the whole deeplink URL at 8,000 characters (encoded). */
export const CURSOR_URL_MAX = 8000;

const CURSOR_APP = "cursor://anysphere.cursor-deeplink/prompt?text=";
const CURSOR_WEB = "https://cursor.com/link/prompt?text=";
const CLAUDE_CLI = "claude-cli://open?q=";
const CLAUDE_VSCODE = "vscode://anthropic.claude-code/open?q=";

// Every C0 control plus DEL, except \n (0x0A) which we keep. \r (0x0D) is inside this
// range on purpose: CRLF is folded to \n first, so any surviving \r is stray — and it
// would encode to %0D, the byte that makes Claude Code reject the whole URL.
const C0_EXCEPT_LF = /[\u0000-\u0009\u000B-\u001F\u007F]/g;

/**
 * Make a prompt safe to carry in a deep link.
 *
 * Claude Code rejects any URL containing control characters, and a rejected URL fails
 * *silently* — the click just does nothing. Newlines must survive, though:
 * `encodeURIComponent("\n")` gives `%0A`, which is exactly what the docs prescribe.
 */
export function sanitizePrompt(raw: string): string {
  return raw.replace(/\r\n?/g, "\n").replace(C0_EXCEPT_LF, "");
}

/**
 * Build the "Open in agent" menu for a prompt.
 *
 * Each URL is a literal template plus exactly one `encodeURIComponent` call. That single
 * escape is what stops a plan title like `x&q=evil` from breaking out of the query string —
 * don't refactor it into `URL`/`URLSearchParams`, which normalise custom schemes
 * inconsistently across engines.
 */
export function agentLinks(rawPrompt: string): AgentLink[] {
  const prompt = sanitizePrompt(rawPrompt);
  if (!prompt) return [];

  const encoded = encodeURIComponent(prompt);
  const overClaude = prompt.length > CLAUDE_PROMPT_MAX;
  const claudeReason = `Prompt is over ${CLAUDE_PROMPT_MAX.toLocaleString()} characters — use Copy prompt`;

  const cap = (id: AgentLinkId, label: string, base: string, hint: string): AgentLink => {
    const href = base + encoded;
    return href.length > CURSOR_URL_MAX
      ? {
          id,
          label,
          kind: id === "cursor-web" ? "web" : "deeplink",
          disabled: true,
          reason: `Link is over ${CURSOR_URL_MAX.toLocaleString()} characters — use Copy prompt`,
        }
      : { id, label, kind: id === "cursor-web" ? "web" : "deeplink", href, hint };
  };

  const claude = (id: AgentLinkId, label: string, base: string, hint: string): AgentLink =>
    overClaude
      ? { id, label, kind: "deeplink", disabled: true, reason: claudeReason }
      : { id, label, kind: "deeplink", href: base + encoded, hint };

  return [
    cap("cursor", "Cursor", CURSOR_APP, "Desktop app"),
    claude("claude-code", "Claude Code", CLAUDE_CLI, "Terminal · v2.1.91+ · opens in ~"),
    claude("claude-vscode", "Claude in VS Code", CLAUDE_VSCODE, "Editor tab"),
    cap("cursor-web", "Cursor (web)", CURSOR_WEB, "Sends the prompt to cursor.com"),
    { id: "copy", label: "Copy prompt", kind: "copy", hint: "Works with any agent" },
  ];
}
