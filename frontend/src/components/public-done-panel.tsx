import { Badge } from "@/components/ui";
import { Markdown } from "@/components/markdown";

interface PublicDone {
  summary: string;
  links: { type: string; url: string; label: string }[];
  residual_notes: string | null;
  posted_by_name: string;
  posted_at: string;
}

interface PublicPlan {
  title: string;
  status: string;
  owner_name: string;
  markdown: string;
  done: PublicDone | null;
}

export function PublicDonePanel({ plan }: { plan: PublicPlan }) {
  const done = plan.done;
  if (!done) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{plan.title}</h1>
        <Badge variant="done">Shipped</Badge>
      </div>
      <p className="text-sm text-[var(--muted)]">
        {plan.owner_name} · reported by {done.posted_by_name}
      </p>

      <section className="surface rounded-2xl p-6 md:p-8">
        <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--done)]">
          What shipped
        </p>
        <Markdown content={done.summary} />
      </section>

      {done.links.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {done.links.map((link, i) => (
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

      {done.residual_notes && (
        <section className="rounded-2xl border border-dashed border-[var(--line)] p-5 text-[var(--muted)]">
          <h4 className="mb-2 font-medium text-[var(--ink)]">Residual notes</h4>
          <Markdown content={done.residual_notes} />
        </section>
      )}

      <details className="surface rounded-2xl p-5">
        <summary className="cursor-pointer font-medium">What was planned</summary>
        <div className="mt-4 border-t border-[var(--line)] pt-4">
          <Markdown content={plan.markdown} />
        </div>
      </details>
    </div>
  );
}
