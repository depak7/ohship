import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui";
import { Markdown } from "@/components/markdown";
import { PublicDonePanel } from "@/components/public-done-panel";
import { PlanStatusBadge } from "@/components/plan-panels";
import { PlanStatus, CriterionOutcome } from "@/lib/api";

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

interface PublicDone {
  reconciliation?: CriterionOutcome[];
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

async function fetchPublicPlan(token: string): Promise<PublicPlan | null> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const res = await fetch(`${apiUrl}/api/v1/public/plans/${token}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error("Failed to load shared plan");
  }
  return res.json();
}

export default async function SharedPlanPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  let plan: PublicPlan | null = null;
  let error = "";

  try {
    plan = await fetchPublicPlan(token);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load plan";
  }

  if (error) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <p className="text-[var(--danger)]">{error}</p>
      </main>
    );
  }

  if (!plan) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-2xl font-semibold">Plan not found</h1>
        <p className="mt-2 text-[var(--muted)]">
          This link may have expired or sharing was turned off.
        </p>
      </main>
    );
  }

  const isDone = plan.status === "done" && plan.done;

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <p className="text-sm text-[var(--muted)]">Shared Planlog plan</p>
        <Link href="/login">
          <Button variant="outline">Sign in to comment or review</Button>
        </Link>
      </div>

      {isDone ? (
        <PublicDonePanel plan={plan} />
      ) : (
        <div className="space-y-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight">{plan.title}</h1>
              <p className="mt-2 text-sm text-[var(--muted)]">{plan.owner_name}</p>
            </div>
            <PlanStatusBadge status={plan.status as PlanStatus} />
          </div>
          <section className="surface rounded-2xl p-6 md:p-8">
            <Markdown content={plan.markdown} />
          </section>
        </div>
      )}
    </main>
  );
}
