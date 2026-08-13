"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Button, Card, Label, Textarea } from "@/components/ui";
import { DonePanel, PlanStatusBadge } from "@/components/plan-panels";
import { Markdown } from "@/components/markdown";
import { NotifySidebar } from "@/components/notify-sidebar";
import { ReviewersSidebar } from "@/components/reviewers-sidebar";
import { ensureAnyoneLink, ShareSidebar } from "@/components/share-sidebar";
import { api, DoneLink, Member, PlanDetail } from "@/lib/api";
import { getToken } from "@/lib/auth";

export default function PlanDetailPage() {
  const params = useParams();
  const router = useRouter();
  const planId = params.id as string;

  const [plan, setPlan] = useState<PlanDetail | null>(null);
  const [meId, setMeId] = useState<string | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [comment, setComment] = useState("");
  const [showDoneForm, setShowDoneForm] = useState(false);
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState<"rendered" | "source">("rendered");
  const [doneSummary, setDoneSummary] = useState("");
  const [doneNotes, setDoneNotes] = useState("");
  const [doneLinks, setDoneLinks] = useState("");
  const [handoffNotes, setHandoffNotes] = useState("");
  const [shareLinkCopied, setShareLinkCopied] = useState(false);
  const [notifySummary, setNotifySummary] = useState("");

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
      const [detail, me] = await Promise.all([api.getPlan(planId), api.me()]);
      setPlan(detail);
      setMeId(me.id);
      try {
        setMembers(await api.listMembers(detail.organization_id));
      } catch {
        setMembers([]);
      }
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

  async function copyAgentPrompt() {
    const prompt = plan.agent_prompt;
    if (!prompt) return;
    await navigator.clipboard.writeText(prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const canShip = plan.status !== "done";

  const doneForm = showDoneForm && canShip && (
    <div className="mt-4 space-y-4 border-t border-[var(--line)] pt-4">
      <p className="text-sm text-[var(--muted)]">
        Marks the plan as Done (self-approves and claims if needed). Review steps are optional.
      </p>
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
      <div>
        <Label htmlFor="handoff-notes">Handoff / spec update (markdown)</Label>
        <Textarea
          id="handoff-notes"
          rows={4}
          value={handoffNotes}
          onChange={(e) => setHandoffNotes(e.target.value)}
          placeholder={
            "## For frontend\n\n- API endpoints changed\n- Update spec at …\n- Start from /share/… link"
          }
        />
        <p className="mt-1 text-xs text-[var(--muted)]">
          What the next person needs to implement — shown prominently on the Done report.
        </p>
      </div>
      <Button
        disabled={actionLoading || !doneSummary.trim()}
        onClick={async () => {
          setActionLoading(true);
          setError("");
          try {
            const notifyBefore = plan.notifyees || [];
            const updated = await api.postDone(planId, {
              summary: doneSummary,
              links: parseLinks(doneLinks),
              residual_notes: doneNotes || undefined,
              handoff_notes: handoffNotes.trim() || undefined,
            });
            setPlan(updated);
            setShowDoneForm(false);
            const link = await ensureAnyoneLink(planId);
            const refreshed = await api.getPlan(planId);
            setPlan(refreshed);
            await navigator.clipboard.writeText(link);
            const names = (refreshed.done?.handoff_to || notifyBefore).map((u) => u.name);
            setNotifySummary(
              names.length
                ? `Notified in OhShip: ${names.join(", ")}. Share link copied.`
                : "Share link copied — paste in Slack for people outside the org."
            );
            setShareLinkCopied(true);
            setTimeout(() => {
              setShareLinkCopied(false);
              setNotifySummary("");
            }, 5000);
          } catch (e) {
            setError(e instanceof Error ? e.message : "Action failed");
          } finally {
            setActionLoading(false);
          }
        }}
      >
        Submit Done
      </Button>
      {shareLinkCopied && notifySummary && (
        <p className="text-sm text-[var(--done)]">{notifySummary}</p>
      )}
    </div>
  );

  const sidebars = (
    <div className="space-y-4">
      <ShareSidebar
        plan={plan}
        disabled={actionLoading}
        onUpdate={setPlan}
      />
      <ReviewersSidebar
        plan={plan}
        members={members}
        meId={meId}
        disabled={actionLoading}
        onAdd={async (memberId) => {
          setActionLoading(true);
          setError("");
          try {
            setPlan(await api.requestReviewers(planId, [memberId]));
          } catch (e) {
            setError(e instanceof Error ? e.message : "Could not add reviewer");
          } finally {
            setActionLoading(false);
          }
        }}
        onCopyAgentPrompt={copyAgentPrompt}
        copied={copied}
      />
      <NotifySidebar
        plan={plan}
        members={members}
        meId={meId}
        disabled={actionLoading}
        onAdd={async (memberId) => {
          setActionLoading(true);
          setError("");
          try {
            setPlan(await api.requestNotifyees(planId, [memberId]));
          } catch (e) {
            setError(e instanceof Error ? e.message : "Could not add notifyee");
          } finally {
            setActionLoading(false);
          }
        }}
      />
    </div>
  );

  return (
    <AppShell>
      <Link href="/" className="mb-4 inline-block text-sm text-[var(--muted)] hover:text-[var(--ink)]">
        ← Back to plans
      </Link>

      {plan.status === "done" && plan.done ? (
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_16rem]">
          <DonePanel plan={plan} />
          {sidebars}
        </div>
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight">{plan.title}</h1>
              <p className="mt-2 text-sm text-[var(--muted)]">
                {plan.owner.name}
                {plan.project && (
                  <span className="font-medium text-[var(--ink)]"> · {plan.project}</span>
                )}
                {plan.team && ` · ${plan.team}`}
              </p>
            </div>
            <PlanStatusBadge status={plan.status} />
          </div>

          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_16rem]">
            <div>
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
                  {canShip && (
                    <Button onClick={() => setShowDoneForm(!showDoneForm)}>
                      {showDoneForm ? "Hide Done form" : "Mark as Done"}
                    </Button>
                  )}
                  {(plan.status === "draft" || plan.status === "changes_requested") && (
                    <Button
                      variant="outline"
                      disabled={actionLoading}
                      onClick={() => runAction(() => api.submitPlan(planId))}
                    >
                      {plan.status === "draft" ? "Request review" : "Request review again"}
                    </Button>
                  )}
                  {plan.status === "in_review" && (
                    <>
                      <Button
                        variant="outline"
                        disabled={actionLoading}
                        onClick={() => runAction(() => api.approvePlan(planId))}
                      >
                        Approve only
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
                      variant="outline"
                      disabled={actionLoading}
                      onClick={() => runAction(() => api.claimPlan(planId))}
                    >
                      Claim
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

                {doneForm}
              </Card>
            </div>
            {sidebars}
          </div>
        </>
      )}
    </AppShell>
  );
}
