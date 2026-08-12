import { Badge } from "@/components/ui";
import { PlanDetail, STATUS_LABELS } from "@/lib/api";
import { Markdown } from "@/components/markdown";

export function DonePanel({ plan }: { plan: PlanDetail }) {
  if (!plan.done) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{plan.title}</h1>
        <Badge variant="done">Shipped</Badge>
      </div>

      <section className="surface rounded-2xl p-6 md:p-8">
        <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--done)]">
          What shipped
        </p>
        <Markdown content={plan.done.summary} />
      </section>

      {plan.done.links.length > 0 && (
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

export function PlanStatusBadge({ status }: { status: keyof typeof STATUS_LABELS }) {
  return <Badge variant={status}>{STATUS_LABELS[status]}</Badge>;
}
