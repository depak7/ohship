"use client";

import { useEffect, useId, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui";
import { agentLinks, type AgentLink } from "@/lib/agent-links";
import { cn } from "@/lib/utils";

/**
 * Menu that opens the plan's agent prompt in a coding agent.
 *
 * A browser cannot tell whether `cursor://` or `claude-cli://` is registered, and clicking an
 * unregistered scheme fails silently. Rather than probe for handlers (iframe/blur tricks are
 * unreliable), Copy prompt is always present, and clicking a deep link surfaces a "nothing
 * happened?" hint so the fallback is on screen at the moment the link fails.
 */
export function OpenInAgent({
  prompt,
  variant = "outline",
  align = "left",
  className,
}: {
  prompt?: string;
  variant?: "outline" | "ghost";
  align?: "left" | "right";
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [launched, setLaunched] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!panelRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    menuRef.current?.querySelector<HTMLElement>("[data-item]:not([aria-disabled='true'])")?.focus();
  }, [open]);

  function close() {
    setOpen(false);
    setLaunched(null);
    triggerRef.current?.focus();
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key === "Tab") {
      setOpen(false);
      return;
    }
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();

    const items = Array.from(
      menuRef.current?.querySelectorAll<HTMLElement>("[data-item]:not([aria-disabled='true'])") || []
    );
    if (items.length === 0) return;
    const at = items.indexOf(document.activeElement as HTMLElement);
    const next =
      event.key === "Home" ? 0
      : event.key === "End" ? items.length - 1
      : event.key === "ArrowDown" ? (at + 1) % items.length
      : (at - 1 + items.length) % items.length;
    items[next]?.focus();
  }

  async function copy(text: string) {
    // Copy is the fallback for every agent we can't deep-link into, so it has to survive a
    // denied clipboard permission rather than silently do nothing.
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const scratch = document.createElement("textarea");
      scratch.value = text;
      scratch.setAttribute("readonly", "");
      scratch.style.position = "fixed";
      scratch.style.opacity = "0";
      document.body.appendChild(scratch);
      scratch.select();
      try {
        document.execCommand("copy");
      } finally {
        document.body.removeChild(scratch);
      }
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const links = prompt ? agentLinks(prompt) : [];
  if (links.length === 0) return null;

  const copyItem = links.find((link) => link.kind === "copy");
  const launchable = links.filter((link) => link.kind !== "copy");

  return (
    <div className={cn("relative", className)} ref={panelRef}>
      <Button
        ref={triggerRef}
        type="button"
        variant={variant}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        Open in agent
        <ChevronDown className={cn("h-4 w-4 transition-transform", open && "rotate-180")} />
      </Button>

      {open && (
        <div
          id={panelId}
          ref={menuRef}
          role="menu"
          aria-label="Open this plan in a coding agent"
          onKeyDown={onKeyDown}
          className={cn(
            "absolute z-20 mt-1 w-72 overflow-hidden rounded-xl border border-[var(--line)]",
            "bg-[var(--bg-elevated)] shadow-[var(--shadow)]",
            align === "right" ? "right-0" : "left-0"
          )}
        >
          <ul className="py-1">
            {launchable.map((link) => (
              <li key={link.id}>
                <MenuLink link={link} onLaunch={() => setLaunched(link.label)} />
              </li>
            ))}
          </ul>

          {launched && (
            <p className="border-t border-[var(--line)] bg-[var(--accent-soft)] px-3 py-2 text-xs text-[var(--ink)]">
              Opening {launched}… nothing happened? Use <strong>Copy prompt</strong> below.
            </p>
          )}

          {copyItem && (
            <div className="border-t border-[var(--line)]">
              <button
                type="button"
                data-item
                role="menuitem"
                tabIndex={-1}
                onClick={() => copy(prompt!)}
                className="flex w-full flex-col items-start px-3 py-2 text-left hover:bg-black/5 focus:bg-black/5 focus:outline-none"
              >
                <span className="text-sm font-medium">
                  {copied ? "Copied prompt" : copyItem.label}
                </span>
                <span className="text-xs text-[var(--muted)]">{copyItem.hint}</span>
              </button>
            </div>
          )}

          <p className="border-t border-[var(--line)] px-3 py-2 text-xs text-[var(--muted)]">
            The prompt is pre-filled, never sent — you press Enter. Deep links need the
            desktop app installed.
          </p>
        </div>
      )}
    </div>
  );
}

function MenuLink({ link, onLaunch }: { link: AgentLink; onLaunch: () => void }) {
  if (link.disabled) {
    return (
      <span
        data-item
        role="menuitem"
        aria-disabled="true"
        className="flex flex-col items-start px-3 py-2 opacity-50"
      >
        <span className="text-sm font-medium">{link.label}</span>
        <span className="text-xs text-[var(--muted)]">{link.reason}</span>
      </span>
    );
  }

  // Plain <a>, not next/link: custom schemes must not go through the router. And no
  // target="_blank" on cursor:// or claude-cli://, which leaves an orphan blank tab behind.
  const external = link.kind === "web";
  return (
    <a
      data-item
      role="menuitem"
      tabIndex={-1}
      href={link.href}
      onClick={onLaunch}
      {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      className="flex flex-col items-start px-3 py-2 hover:bg-black/5 focus:bg-black/5 focus:outline-none"
    >
      <span className="text-sm font-medium">{link.label}</span>
      {link.hint && <span className="text-xs text-[var(--muted)]">{link.hint}</span>}
    </a>
  );
}
