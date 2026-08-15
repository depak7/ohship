"use client";

import { useState } from "react";

export const INSTALL_COMMAND = "curl -fsSL https://planlog.depak.dev/install | bash";

function CopyIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
      strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5" aria-hidden>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}
      strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5" aria-hidden>
      <path d="M4 12.5l5.5 5.5L20 6" />
    </svg>
  );
}

/** Terminal-styled install block with the copy control inside the window chrome. */
export function InstallCommand({ className = "" }: { className?: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(INSTALL_COMMAND);
    } catch {
      return;
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className={className}>
      <div className="overflow-hidden rounded-2xl border border-black/10 bg-[#121a16] shadow-[0_28px_70px_-30px_rgba(23,33,27,0.6)]">
        <div className="flex items-center gap-2 border-b border-white/10 bg-[#1b2621] px-3 py-2">
          <span className="flex gap-1.5" aria-hidden>
            <i className="h-2.5 w-2.5 rounded-full bg-[#f0655a]" />
            <i className="h-2.5 w-2.5 rounded-full bg-[#f3bd4e]" />
            <i className="h-2.5 w-2.5 rounded-full bg-[#4fc08d]" />
          </span>
          <span className="flex-1 text-center font-mono text-[0.7rem] tracking-wide text-[#8ea296]">
            your-repo — bash
          </span>
          <button
            type="button"
            onClick={copy}
            aria-label="Copy install command"
            className={`inline-flex items-center gap-1.5 rounded-lg border px-2 py-1 text-[0.7rem] font-medium transition ${
              copied
                ? "border-[#4fc08d]/50 bg-[#4fc08d]/10 text-[#4fc08d]"
                : "border-white/10 bg-white/5 text-[#8ea296] hover:border-white/25 hover:bg-white/10 hover:text-white"
            }`}
          >
            {copied ? <CheckIcon /> : <CopyIcon />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <pre className="overflow-x-auto px-4 py-3 font-mono text-sm leading-relaxed text-[#e8efe9]">
          <code>
            <span className="mr-2 select-none text-[#4fc08d]">$</span>
            curl <span className="text-[#f3bd4e]">-fsSL</span>{" "}
            <span className="text-[#7fb3f5]">https://planlog.depak.dev/install</span> | bash
          </code>
        </pre>
      </div>
      <p className="mt-2 text-sm text-[#5d6b60]">
        Asks where to install (this project or laptop-wide) and which agents to wire up — Cursor,
        Claude Code, Codex, Gemini CLI, Copilot, Windsurf. Skip the prompts with{" "}
        <code className="rounded bg-black/5 px-1 py-0.5 text-[#3d4a40]">
          | bash -s -- --global --agent claude
        </code>
        .
      </p>
    </div>
  );
}
