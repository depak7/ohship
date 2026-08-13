"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui";
import { Member, PlanDetail, UserBrief } from "@/lib/api";

export function ReviewersSidebar({
  plan,
  members,
  meId,
  disabled,
  onAdd,
  onCopyAgentPrompt,
  copied,
}: {
  plan: PlanDetail;
  members: Member[];
  meId: string | null;
  disabled?: boolean;
  onAdd: (memberId: string) => Promise<void>;
  onCopyAgentPrompt: () => void;
  copied: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [addingId, setAddingId] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const askedIds = new Set((plan.reviewers || []).map((r) => r.id));
  const candidates = members.filter((m) => m.id !== meId && !askedIds.has(m.id));
  const canEdit =
    plan.status === "draft" ||
    plan.status === "changes_requested" ||
    plan.status === "in_review";

  useEffect(() => {
    function onDocClick(event: MouseEvent) {
      if (!panelRef.current?.contains(event.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  async function add(memberId: string) {
    setAddingId(memberId);
    try {
      await onAdd(memberId);
      setOpen(false);
    } finally {
      setAddingId(null);
    }
  }

  return (
    <aside className="surface rounded-2xl p-5">
      <div className="relative" ref={panelRef}>
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">Reviewers</h2>
          {canEdit && (
            <button
              type="button"
              className="rounded-lg px-2 py-1 text-xs font-medium text-[var(--muted)] hover:bg-black/5 hover:text-[var(--ink)]"
              onClick={() => setOpen((value) => !value)}
              aria-label="Add reviewer"
            >
              Add
            </button>
          )}
        </div>

        {open && (
          <div className="absolute right-0 z-20 mt-1 w-64 overflow-hidden rounded-xl border border-[var(--line)] bg-[var(--bg-elevated)] shadow-[var(--shadow)]">
            <p className="border-b border-[var(--line)] px-3 py-2 text-xs font-medium text-[var(--muted)]">
              Request review from
            </p>
            {candidates.length === 0 ? (
              <div className="space-y-2 px-3 py-3 text-sm text-[var(--muted)]">
                {members.filter((m) => m.id !== meId).length === 0 ? (
                  <>
                    <p>No other members in this organization yet.</p>
                    <Link href="/orgs" className="text-[var(--accent)] hover:underline">
                      Invite teammates
                    </Link>
                  </>
                ) : (
                  <p>Everyone else is already a reviewer.</p>
                )}
              </div>
            ) : (
              <ul className="max-h-64 overflow-y-auto py-1">
                {candidates.map((member) => (
                  <li key={member.id}>
                    <button
                      type="button"
                      disabled={disabled || addingId === member.id}
                      onClick={() => add(member.id)}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-black/5 disabled:opacity-50"
                    >
                      <Avatar name={member.name} url={member.avatar_url} />
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{member.name}</span>
                        <span className="block truncate text-xs text-[var(--muted)]">
                          {member.email}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {(plan.reviewers || []).length === 0 ? (
        <p className="text-sm text-[var(--muted)]">No reviewers yet.</p>
      ) : (
        <ul className="space-y-3">
          {(plan.reviewers || []).map((reviewer) => (
            <li key={reviewer.id} className="flex items-center gap-2">
              <Avatar name={reviewer.name} url={reviewer.avatar_url} />
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{reviewer.name}</p>
                <p className="text-xs text-[var(--muted)]">Awaiting review</p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 border-t border-[var(--line)] pt-3">
        <Button variant="outline" className="w-full text-xs" onClick={onCopyAgentPrompt}>
          {copied ? "Copied prompt" : "Copy agent prompt"}
        </Button>
        <p className="mt-2 text-xs text-[var(--muted)]">
          Copies a prompt for review or ship workflow with OhShip MCP.
        </p>
      </div>
    </aside>
  );
}

function Avatar({ name, url }: { name: string; url?: string | null }) {
  if (url) {
    return (
      <img
        src={url}
        alt=""
        className="h-7 w-7 shrink-0 rounded-full object-cover"
      />
    );
  }
  return (
    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--accent-soft)] text-xs font-semibold text-[var(--accent)]">
      {initials(name)}
    </span>
  );
}

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

export function ReviewerNames({ reviewers }: { reviewers?: UserBrief[] }) {
  if (!reviewers?.length) return null;
  return <span> · review: {reviewers.map((r) => r.name).join(", ")}</span>;
}
