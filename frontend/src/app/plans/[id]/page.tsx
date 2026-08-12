"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Button, Card, Label, Textarea } from "@/components/ui";
import { DonePanel, PlanStatusBadge } from "@/components/plan-panels";
import { Markdown } from "@/components/markdown";
import { api, DoneLink, PlanDetail } from "@/lib/api";
import { getToken } from "@/lib/auth";

export default function PlanDetailPage() {
  const params = useParams();
  const router = useRouter();
  const planId = params.id as string;

  const [plan, setPlan] = useState<PlanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [comment, setComment] = useState("");
  const [showDoneForm, setShowDoneForm] = useState(false);
  const [viewMode, setViewMode] = useState<"rendered" | "source">("rendered");
  const [doneSummary, setDoneSummary] = useState("");
  const [doneNotes, setDoneNotes] = useState("");
  const [doneLinks, setDoneLinks] = useState("");

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    loadPlan();
  }, [planId, router]);

  async function loadPlan() {
    setLoading(true);
    setError("");
    try {
      setPlan(await api.getPlan(planId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load plan");
    } finally {
      setLoading(false);
    }
  }

  async function runAction(fn: () => Promise<PlanDetail>) {
    setActionLoading(true);
    setError("");
    try {
      setPlan(await fn());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setActionLoading(false);
    }
  }

  function parseLinks(raw: string): DoneLink[] {
    if (!raw.trim()) return [];
    return raw
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [type, url, ...labelParts] = line.split("|");
        return {
          type: type.trim(),
          url: (url || "").trim(),
          label: labelParts.join("|").trim() || type.trim(),
        };
      });
  }

  if (loading) {
    return (
      <AppShell>
        <p className="text-[var(--muted)]">Loading plan…</p>
      </AppShell>
    );
  }

  if (!plan) {
    return (
      <AppShell>
        <p className="text-[var(--danger)]">{error || "Plan not found"}</p>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <Link href="/" className="mb-4 inline-block text-sm text-[var(--muted)] hover:text-[var(--ink)]">
        ← Back to plans
      </Link>

      {plan.status === "done" && plan.done ? (
        <DonePanel plan={plan} />
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight">{plan.title}</h1>
              <p className="mt-2 text-sm text-[var(--muted)]">
                {plan.owner.name}
                {plan.team && ` · ${plan.team}`}
                {plan.project && ` · ${plan.project}`}
              </p>
            </div>
            <PlanStatusBadge status={plan.status} />
          </div>

          <div className="mb-4 flex gap-2">
            <Button
              variant={viewMode === "rendered" ? "default" : "outline"}
              onClick={() => setViewMode("rendered")}
            >
              Rendered MD
            </Button>
            <Button
              variant={viewMode === "source" ? "default" : "outline"}
              onClick={() => setViewMode("source")}
            >
              Source
            </Button>
          </div>

          <Card className="mb-6 md:p-8">
            {viewMode === "rendered" ? (
              <Markdown content={plan.markdown} />
            ) : (
              <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-sm text-[var(--muted)]">
                {plan.markdown}
              </pre>
            )}
          </Card>

          {plan.suggestions.length > 0 && (
            <Card className="mb-6">
              <h2 className="mb-4 font-semibold">Suggestions</h2>
              <div className="space-y-4">
                {plan.suggestions.map((s) => (
                  <div key={s.id} className="border-l-2 border-[var(--warn)] pl-4">
                    <p className="text-xs text-[var(--muted)]">
                      {s.author.name} · {new Date(s.created_at).toLocaleString()}
                    </p>
                    <Markdown content={s.content} />
                  </div>
                ))}
              </div>
            </Card>
          )}

          {error && <p className="mb-4 text-sm text-[var(--danger)]">{error}</p>}

          <Card>
            <h2 className="mb-4 font-semibold">Actions</h2>
            <div className="flex flex-wrap gap-2">
              {(plan.status === "draft" || plan.status === "changes_requested") && (
                <Button
                  disabled={actionLoading}
                  onClick={() => runAction(() => api.submitPlan(planId))}
                >
                  {plan.status === "draft" ? "Submit for review" : "Resubmit for review"}
                </Button>
              )}
              {plan.status === "in_review" && (
                <>
                  <Button
                    disabled={actionLoading}
                    onClick={() => runAction(() => api.approvePlan(planId))}
                  >
                    Approve
                  </Button>
                  <Button
                    variant="outline"
                    disabled={actionLoading}
                    onClick={() =>
                      runAction(() => api.requestChanges(planId, comment || undefined))
                    }
                  >
                    Request changes
                  </Button>
                </>
              )}
              {plan.status === "approved" && (
                <Button
                  disabled={actionLoading}
                  onClick={() => runAction(() => api.claimPlan(planId))}
                >
                  Claim
                </Button>
              )}
              {plan.status === "in_progress" && (
                <Button variant="outline" onClick={() => setShowDoneForm(!showDoneForm)}>
                  Post Done
                </Button>
              )}
            </div>

            {plan.status === "in_review" && (
              <div className="mt-4">
                <Label htmlFor="comment">Comment (optional)</Label>
                <Textarea
                  id="comment"
                  rows={3}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Suggest changes in markdown…"
                />
              </div>
            )}

            {showDoneForm && plan.status === "in_progress" && (
              <div className="mt-4 space-y-4 border-t border-[var(--line)] pt-4">
                <div>
                  <Label htmlFor="summary">Summary (markdown)</Label>
                  <Textarea
                    id="summary"
                    rows={5}
                    value={doneSummary}
                    onChange={(e) => setDoneSummary(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="links">Links (type|url|label per line)</Label>
                  <Textarea
                    id="links"
                    rows={3}
                    value={doneLinks}
                    onChange={(e) => setDoneLinks(e.target.value)}
                    placeholder={"pr|https://github.com/org/repo/pull/1|PR #1"}
                  />
                </div>
                <div>
                  <Label htmlFor="residual">Residual notes</Label>
                  <Textarea
                    id="residual"
                    rows={2}
                    value={doneNotes}
                    onChange={(e) => setDoneNotes(e.target.value)}
                  />
                </div>
                <Button
                  disabled={actionLoading || !doneSummary.trim()}
                  onClick={() =>
                    runAction(() =>
                      api.postDone(planId, {
                        summary: doneSummary,
                        links: parseLinks(doneLinks),
                        residual_notes: doneNotes || undefined,
                      })
                    )
                  }
                >
                  Submit Done
                </Button>
              </div>
            )}
          </Card>
        </>
      )}
    </AppShell>
  );
}
