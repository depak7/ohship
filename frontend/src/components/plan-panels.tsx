"use client";

import { useState } from "react";
import { Badge, Button } from "@/components/ui";
import { CriterionOutcome, CriterionStatus, PlanDetail, STATUS_LABELS } from "@/lib/api";
import { Markdown } from "@/components/markdown";
import { ensureAnyoneLink } from "@/components/share-sidebar";
import { formatWhen } from "@/lib/utils";

export function DonePanel({ plan }: { plan: PlanDetail }) {
  const [copied, setCopied] = useState<"link" | "handoff" | null>(null);

  if (!plan.done) return null;

  const handoffRecipients = plan.done.handoff_to || [];

  async function copyShareLink() {
    const link = plan.share_url || (await ensureAnyoneLink(plan.id));
    await navigator.clipboard.writeText(link);
    setCopied("link");
    setTimeout(() => setCopied(null), 2500);
  }

  async function copyHandoffMessage() {
    const link = plan.share_url || (await ensureAnyoneLink(plan.id));
    const lines = [
      `Done: ${plan.title}`,
      plan.project ? `Project: ${plan.project}` : "",
      "",
      plan.done!.handoff_notes?.trim() || plan.done!.summary.trim(),
      "",
      plan.done!.links.length
        ? "Links:\n" + plan.done!.links.map((l) => `- ${l.label || l.type}: ${l.url}`).join("\n")
        : "",
      "",
      `Read full report: ${link}`,
    ].filter(Boolean);
    await navigator.clipboard.writeText(lines.join("\n"));
    setCopied("handoff");
    setTimeout(() => setCopied(null), 2500);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-semibold tracking-tight">{plan.title}</h1>
            <Badge variant="done">Shipped</Badge>
          </div>
          <p className="mt-2 text-sm text-[var(--muted)]">
            {plan.project && (
              <span className="font-medium text-[var(--ink)]">{plan.project}</span>
            )}
            {plan.project && " · "}
            Shipped by {plan.done.posted_by.name} · {formatWhen(plan.done.posted_at)}
          </p>
          <PlanLifecycle plan={plan} />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" className="text-xs" onClick={copyShareLink}>
            {copied === "link" ? "Copied link" : "Copy share link"}
          </Button>
          <Button variant="outline" className="text-xs" onClick={copyHandoffMessage}>
            {copied === "handoff" ? "Copied message" : "Copy for Slack"}
          </Button>
        </div>
      </div>

      {handoffRecipients.length > 0 && (
        <section className="rounded-2xl border border-[var(--accent-soft)] bg-[var(--accent-soft)]/40 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">
            Notified in Planlog
          </p>
          <p className="mt-2 text-sm">
            {handoffRecipients.map((u) => u.name).join(", ")} — check{" "}
            <span className="font-medium">Sent to me</span> on the plans list.
          </p>
        </section>
      )}

      <section className="surface rounded-2xl p-6 md:p-8">
        <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--done)]">
          What shipped
        </p>
        <Markdown content={plan.done.summary} />
      </section>

      <Reconciliation outcomes={plan.done.reconciliation} />

      {plan.done.handoff_notes && (
        <section className="surface rounded-2xl border-l-4 border-l-[var(--accent)] p-6 md:p-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">
            For the next person (spec / handoff)
          </p>
          <Markdown content={plan.done.handoff_notes} />
        </section>
      )}

      {plan.done.links.length > 0 && (
        <section>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-[var(--muted)]">
            Links
          </p>
          <div className="flex flex-wrap gap-2">
            {plan.done.links.map((link, i) => (
              <a
                key={i}
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-full border border-[var(--line)] bg-white/70 px-3 py-1.5 text-sm hover:bg-white"
              >
                {link.label || link.type}
              </a>
            ))}
          </div>
        </section>
      )}

      {plan.done.residual_notes && (
        <section className="rounded-2xl border border-dashed border-[var(--line)] p-5 text-[var(--muted)]">
          <h4 className="mb-2 font-medium text-[var(--ink)]">Residual notes</h4>
          <Markdown content={plan.done.residual_notes} />
        </section>
      )}

      <details className="surface rounded-2xl p-5">
        <summary className="cursor-pointer font-medium">What was planned</summary>
        <div className="mt-4 border-t border-[var(--line)] pt-4">
          <Markdown content={plan.markdown || plan.intent} />
        </div>
      </details>
    </div>
  );
}

const OUTCOME_STYLE: Record<CriterionStatus, { label: string; className: string; mark: string }> = {
  met: { label: "Met", className: "text-[var(--accent)]", mark: "✓" },
  changed: { label: "Changed", className: "text-[var(--warn)]", mark: "~" },
  dropped: { label: "Dropped", className: "text-[var(--danger)]", mark: "×" },
  unreported: { label: "Not reported", className: "text-[var(--muted)]", mark: "?" },
  extra: { label: "Not in plan", className: "text-[var(--muted)]", mark: "+" },
};

/**
 * What happened to each acceptance criterion.
 *
 * The point of the section is the rows that aren't "met" — a Done summary can read perfectly
 * while quietly having dropped a criterion, and that is the drift this makes visible.
 */
export function Reconciliation({
  outcomes,
  showNotes = true,
}: {
  outcomes?: CriterionOutcome[];
  showNotes?: boolean;
}) {
  if (!outcomes || outcomes.length === 0) {
    return (
      <section className="rounded-2xl border border-dashed border-[var(--line)] p-5 text-sm text-[var(--muted)]">
        <span className="font-medium text-[var(--ink)]">Not reconciled.</span> This Done didn&apos;t
        report against the plan&apos;s acceptance criteria, so what shipped hasn&apos;t been checked
        off against what was approved.
      </section>
    );
  }

  const drifted = outcomes.filter((o) => o.status === "changed" || o.status === "dropped").length;
  const met = outcomes.filter((o) => o.status === "met").length;

  return (
    <section className="surface rounded-2xl p-6 md:p-8">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--done)]">
          Against the plan
        </p>
        <p className="text-xs text-[var(--muted)]">
          {met}/{outcomes.length} met
          {drifted > 0 && (
            <span className="font-medium text-[var(--warn)]"> · {drifted} drifted</span>
          )}
        </p>
      </div>
      <ul className="space-y-3">
        {outcomes.map((o, i) => {
          const style = OUTCOME_STYLE[o.status] || OUTCOME_STYLE.unreported;
          return (
            <li key={i} className="flex gap-3 text-sm">
              <span className={`mt-0.5 w-4 shrink-0 text-center font-semibold ${style.className}`}>
                {style.mark}
              </span>
              <div className="min-w-0">
                <p className={o.status === "dropped" ? "text-[var(--muted)] line-through" : ""}>
                  {o.criterion}
                </p>
                <p className={`text-xs ${style.className}`}>
                  {style.label}
                  {showNotes && o.note ? (
                    <span className="text-[var(--muted)]"> — {o.note}</span>
                  ) : null}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function PlanStatusBadge({ status }: { status: keyof typeof STATUS_LABELS }) {
  return <Badge variant={status}>{STATUS_LABELS[status]}</Badge>;
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}
      strokeLinecap="round" strokeLinejoin="round" className="h-3 w-3" aria-hidden>
      <path d="M4 12.5l5.5 5.5L20 6" />
    </svg>
  );
}

function Fact({
  label,
  children,
  tone = "muted",
}: {
  label: string;
  children: React.ReactNode;
  tone?: "muted" | "accent" | "warn";
}) {
  return (
    <span className="inline-flex items-baseline gap-1.5">
      <span className="text-[var(--muted)]">{label}</span>
      <span
        className={
          tone === "accent"
            ? "font-medium text-[var(--accent)]"
            : tone === "warn"
              ? "font-medium text-[var(--warn)]"
              : "font-medium text-[var(--ink)]"
        }
      >
        {children}
      </span>
    </span>
  );
}

/**
 * Who did what, and when. `approved_by`, `approved_at` and `claimed_by` all come down on the
 * plan payload but had no home in the UI, so an approved plan looked identical to one nobody
 * had touched.
 */
export function PlanLifecycle({ plan }: { plan: PlanDetail }) {
  const approved = plan.approved_by;
  const claimed = plan.claimed_by;
  if (!approved && !claimed) return null;

  // Only a peer approval earns the green tick. Showing "✓ Approved by X" for a plan its own
  // author waved through — or one nobody looked at — is the thing that makes an approval
  // record worthless.
  const kind = plan.approval_kind;
  const peer = kind === "peer";

  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-sm">
      {approved && (
        <span className="inline-flex flex-wrap items-center gap-1.5">
          <span className={peer ? "text-[var(--accent)]" : "text-[var(--warn)]"}>
            {peer ? <CheckIcon /> : <span className="text-xs font-semibold">!</span>}
          </span>
          {kind === "on_ship" ? (
            <span className="font-medium text-[var(--warn)]">Shipped without review</span>
          ) : kind === "self" ? (
            <Fact label="Self-approved by" tone="warn">
              {approved.name}
            </Fact>
          ) : (
            <Fact label="Approved by" tone="accent">
              {approved.name}
            </Fact>
          )}
          {plan.approved_at && (
            <span className="text-[var(--muted)]">· {formatWhen(plan.approved_at)}</span>
          )}
          {!peer && (
            <span className="text-xs text-[var(--muted)]">
              {kind === "on_ship"
                ? "— approval was recorded automatically at Done"
                : "— the plan's author approved their own work"}
            </span>
          )}
        </span>
      )}
      {claimed && <Fact label="Claimed by">{claimed.name}</Fact>}
    </div>
  );
}
