"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, PlanStatus, PlanSummary, STATUS_LABELS } from "@/lib/api";
import { getOrgId, getToken } from "@/lib/auth";
import { AppShell } from "@/components/app-shell";
import { Button, Card, Input, Select } from "@/components/ui";
import { PlanStatusBadge } from "@/components/plan-panels";

export default function HomePage() {
  const router = useRouter();
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState<PlanStatus | "">("");
  const [teamFilter, setTeamFilter] = useState("");
  const [requestedOfMe, setRequestedOfMe] = useState(false);
  const [sentToMe, setSentToMe] = useState(false);
  const [meId, setMeId] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    if (!getOrgId()) {
      router.replace("/orgs/new");
      return;
    }
    loadPlans();
  }, [router, statusFilter, teamFilter, requestedOfMe, sentToMe]);

  async function loadPlans() {
    setLoading(true);
    setError("");
    try {
      const me = meId ? { id: meId } : await api.me();
      if (!meId) setMeId(me.id);
      const params: Record<string, string> = {};
      if (statusFilter) params.status = statusFilter;
      if (teamFilter) params.team = teamFilter;
      if (requestedOfMe) params.reviewer_id = me.id;
      if (sentToMe) params.handoff_to = "me";
      const data = await api.listPlans(params);
      setPlans(data.plans);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load plans");
    } finally {
      setLoading(false);
    }
  }

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  return (
    <AppShell>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Plans</h1>
          <p className="mt-2 max-w-xl text-[var(--muted)]">
            Readable markdown plans for humans and agents. Review, claim, and keep Done as history.
          </p>
        </div>
        <Link href="/plans/new">
          <Button>New plan</Button>
        </Link>
      </div>

      <Card className="mb-6">
        <div className="flex flex-wrap gap-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--muted)]">Status</label>
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as PlanStatus | "")}
            >
              <option value="">All</option>
              {(Object.keys(STATUS_LABELS) as PlanStatus[]).map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s]}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 pb-2 text-sm text-[var(--muted)]">
              <input
                type="checkbox"
                checked={requestedOfMe}
                onChange={(e) => setRequestedOfMe(e.target.checked)}
              />
              Requested of me
            </label>
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 pb-2 text-sm text-[var(--muted)]">
              <input
                type="checkbox"
                checked={sentToMe}
                onChange={(e) => setSentToMe(e.target.checked)}
              />
              Sent to me
            </label>
          </div>
          <div className="min-w-[200px] flex-1">
            <label className="mb-1 block text-xs font-medium text-[var(--muted)]">Team</label>
            <Input
              placeholder="Filter by team…"
              value={teamFilter}
              onChange={(e) => setTeamFilter(e.target.value)}
            />
          </div>
        </div>
      </Card>

      {loading && <p className="text-[var(--muted)]">Loading plans…</p>}
      {error && <p className="text-[var(--danger)]">{error}</p>}

      {!loading && !error && plans.length === 0 && (
        <Card>
          <p className="text-[var(--muted)]">
            No plans yet. Create one as a markdown document for your team.
          </p>
        </Card>
      )}

      <div className="space-y-3">
        {plans.map((plan) => (
          <Link key={plan.id} href={`/plans/${plan.id}`}>
            <article className="surface mb-3 rounded-2xl p-5 transition hover:-translate-y-0.5 hover:bg-white">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold tracking-tight">{plan.title}</h2>
                  <p className="mt-1 text-sm text-[var(--muted)]">
                    {plan.owner.name}
                    {plan.team && ` · ${plan.team}`}
                    {plan.project && ` · ${plan.project}`}
                    {plan.reviewers && plan.reviewers.length > 0 &&
                      ` · review: ${plan.reviewers.map((r) => r.name).join(", ")}`}
                  </p>
                </div>
                <div className="text-right">
                  <PlanStatusBadge status={plan.status} />
                  <p className="mt-2 text-xs text-[var(--muted)]">{formatDate(plan.updated_at)}</p>
                </div>
              </div>
            </article>
          </Link>
        ))}
      </div>
    </AppShell>
  );
}
