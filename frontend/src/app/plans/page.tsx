"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, PlanStatus, PlanSummary, STATUS_LABELS } from "@/lib/api";
import { getOrgId, getProject, getToken, setProject, clearProject } from "@/lib/auth";
import { AppShell } from "@/components/app-shell";
import { Button, Card, Select } from "@/components/ui";
import { PlanStatusBadge } from "@/components/plan-panels";

const ALL_PROJECTS = "";

export default function PlansPage() {
  const router = useRouter();
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [projects, setProjects] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState<PlanStatus | "">("");
  const [projectFilter, setProjectFilter] = useState<string>(() => getProject() || "");
  const [requestedOfMe, setRequestedOfMe] = useState(false);
  const [sentToMe, setSentToMe] = useState(false);
  const [meId, setMeId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

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

    function onProjectChange() {
      setProjectFilter(getProject() || "");
    }
    window.addEventListener("planlog-project-change", onProjectChange);
    return () => window.removeEventListener("planlog-project-change", onProjectChange);
  }, [router, statusFilter, projectFilter, requestedOfMe, sentToMe]);

  async function loadPlans() {
    setLoading(true);
    setError("");
    try {
      const me = meId ? { id: meId } : await api.me();
      if (!meId) setMeId(me.id);
      const [projectList, data] = await Promise.all([
        api.listProjects(),
        api.listPlans({
          ...(statusFilter ? { status: statusFilter } : {}),
          ...(projectFilter ? { project: projectFilter } : {}),
          ...(requestedOfMe ? { reviewer_id: me.id } : {}),
          ...(sentToMe ? { handoff_to: "me" } : {}),
        }),
      ]);
      setProjects(projectList);
      setPlans(data.plans);

      if (projectFilter && !projectList.includes(projectFilter)) {
        clearProjectFilter();
      } else if (!projectFilter && projectList.length === 1) {
        selectProject(projectList[0]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load plans");
    } finally {
      setLoading(false);
    }
  }

  function clearProjectFilter() {
    setProjectFilter(ALL_PROJECTS);
    clearProject();
  }

  function selectProject(name: string) {
    setProjectFilter(name);
    if (name) setProject(name);
    else clearProject();
    window.dispatchEvent(new Event("planlog-project-change"));
  }

  const groupedPlans = useMemo(() => {
    if (projectFilter) return null;
    const groups = new Map<string, PlanSummary[]>();
    for (const plan of plans) {
      const key = plan.project?.trim() || "Unassigned";
      const list = groups.get(key) || [];
      list.push(plan);
      groups.set(key, list);
    }
    return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [plans, projectFilter]);

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  async function deletePlan(plan: PlanSummary) {
    if (!window.confirm(`Delete "${plan.title}"? This cannot be undone.`)) {
      return;
    }
    setDeletingId(plan.id);
    setError("");
    try {
      await api.deletePlan(plan.id);
      setPlans((current) => current.filter((p) => p.id !== plan.id));
      setProjects((current) => {
        const stillUsed = plans.some(
          (p) => p.id !== plan.id && p.project === plan.project
        );
        if (plan.project && !stillUsed) {
          return current.filter((name) => name !== plan.project);
        }
        return current;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete plan");
    } finally {
      setDeletingId(null);
    }
  }

  const newPlanHref = projectFilter
    ? `/plans/new?project=${encodeURIComponent(projectFilter)}`
    : "/plans/new";

  return (
    <AppShell>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            {projectFilter ? projectFilter : "Plans"}
          </h1>
          <p className="mt-2 max-w-xl text-[var(--muted)]">
            {projectFilter
              ? "Plans for this project — shared context for everyone working on it."
              : "Browse by project. Pick one to focus; team is optional metadata."}
          </p>
        </div>
        <Link href={newPlanHref}>
          <Button>New plan</Button>
        </Link>
      </div>

      <Card className="mb-6">
        <div className="flex flex-wrap gap-4">
          <div className="min-w-[180px]">
            <label className="mb-1 block text-xs font-medium text-[var(--muted)]">Project</label>
            <Select
              value={projectFilter}
              onChange={(e) => selectProject(e.target.value)}
            >
              <option value={ALL_PROJECTS}>All projects</option>
              {projects.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Select>
          </div>
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
        </div>
      </Card>

      {loading && <p className="text-[var(--muted)]">Loading plans…</p>}
      {error && <p className="text-[var(--danger)]">{error}</p>}

      {!loading && !error && plans.length === 0 && (
        <Card>
          <p className="text-[var(--muted)]">
            {projectFilter
              ? `No plans in ${projectFilter} yet.`
              : "No plans yet. Create one under a project your team shares."}
          </p>
        </Card>
      )}

      {!loading && !error && projectFilter && (
        <PlanList plans={plans} deletingId={deletingId} onDelete={deletePlan} formatDate={formatDate} />
      )}

      {!loading && !error && !projectFilter && groupedPlans && (
        <div className="space-y-8">
          {groupedPlans.map(([projectName, projectPlans]) => (
            <section key={projectName}>
              <div className="mb-3 flex items-center justify-between gap-4">
                <h2 className="text-lg font-semibold tracking-tight">{projectName}</h2>
                <button
                  type="button"
                  className="text-sm text-[var(--accent)] hover:underline"
                  onClick={() => selectProject(projectName === "Unassigned" ? "" : projectName)}
                >
                  Focus this project
                </button>
              </div>
              <PlanList
                plans={projectPlans}
                deletingId={deletingId}
                onDelete={deletePlan}
                formatDate={formatDate}
              />
            </section>
          ))}
        </div>
      )}
    </AppShell>
  );
}

function PlanList({
  plans,
  deletingId,
  onDelete,
  formatDate,
}: {
  plans: PlanSummary[];
  deletingId: string | null;
  onDelete: (plan: PlanSummary) => void;
  formatDate: (iso: string) => string;
}) {
  return (
    <div className="space-y-3">
      {plans.map((plan) => (
        <article
          key={plan.id}
          className="surface mb-3 flex items-start gap-2 rounded-2xl p-5 transition hover:bg-white"
        >
          <Link href={`/plans/${plan.id}`} className="min-w-0 flex-1 hover:-translate-y-0.5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold tracking-tight">{plan.title}</h2>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  {plan.owner.name}
                  {plan.project && (
                    <span className="font-medium text-[var(--ink)]"> · {plan.project}</span>
                  )}
                  {plan.team && ` · ${plan.team}`}
                  {plan.reviewers && plan.reviewers.length > 0 &&
                    ` · review: ${plan.reviewers.map((r) => r.name).join(", ")}`}
                </p>
              </div>
              <div className="text-right">
                <PlanStatusBadge status={plan.status} />
                <p className="mt-2 text-xs text-[var(--muted)]">{formatDate(plan.updated_at)}</p>
              </div>
            </div>
          </Link>
          <button
            type="button"
            aria-label={`Delete ${plan.title}`}
            disabled={deletingId === plan.id}
            onClick={() => onDelete(plan)}
            className="mt-0.5 shrink-0 rounded-lg p-2 text-[var(--muted)] hover:bg-[var(--danger)]/10 hover:text-[var(--danger)] disabled:opacity-50"
          >
            <TrashIcon />
          </button>
        </article>
      ))}
    </div>
  );
}

function TrashIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M3 6h18" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}
