"use client";

import { useState } from "react";
import { Button } from "@/components/ui";

export const INSTALL_COMMAND = "curl -fsSL https://planlog.depak.dev/install | bash";
const NON_INTERACTIVE_HINT = "… | bash -s -- --global --agent claude --agent cursor";

export function InstallCommand({ className = "" }: { className?: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(INSTALL_COMMAND);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className={className}>
      <pre className="overflow-x-auto rounded-xl bg-[#1a2420] px-4 py-3 text-sm text-[#e8efe9]">
        <code>{INSTALL_COMMAND}</code>
      </pre>
      <p className="mt-2 text-sm text-[#5d6b60]">
        Asks where to install (this project or laptop-wide) and which agents to wire up —
        Cursor, Claude Code, Codex, Gemini CLI, Copilot, Windsurf. To skip the prompts:{" "}
        <code className="text-[#3d4a40]">{NON_INTERACTIVE_HINT}</code>
      </p>
      <Button type="button" variant="outline" className="mt-3" onClick={copy}>
        {copied ? "Copied" : "Copy install command"}
      </Button>
    </div>
  );
}
