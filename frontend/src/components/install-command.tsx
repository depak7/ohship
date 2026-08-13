"use client";

import { useState } from "react";
import { Button } from "@/components/ui";

export const INSTALL_COMMAND = "curl -fsSL https://planlog.depak.dev/install | bash";

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
      <Button type="button" variant="outline" className="mt-3" onClick={copy}>
        {copied ? "Copied" : "Copy install command"}
      </Button>
    </div>
  );
}
