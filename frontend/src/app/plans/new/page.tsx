"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Button, Card, Input, Label, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { getOrgId } from "@/lib/auth";

export default function NewPlanPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [intent, setIntent] = useState("");
  const [scope, setScope] = useState("");
  const [acceptanceCriteria, setAcceptanceCriteria] = useState("");
  const [team, setTeam] = useState("");
  const [project, setProject] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const organization_id = getOrgId();
    if (!organization_id) {
      setError("Select or create an organization first");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const plan = await api.createPlan({
        title,
        intent,
        acceptance_criteria: acceptanceCriteria,
        scope: scope || undefined,
        team: team || undefined,
        project: project || undefined,
        organization_id,
      });
      router.push(`/plans/${plan.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create plan");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <Link href="/" className="mb-4 inline-block text-sm text-[var(--muted)] hover:text-[var(--ink)]">
        ← Back to plans
      </Link>
      <h1 className="mb-2 text-3xl font-semibold tracking-tight">New plan</h1>
      <p className="mb-6 text-[var(--muted)]">
        Write in markdown. Your teammates and agents will read the same document.
      </p>
      <Card className="max-w-3xl">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="title">Title</Label>
            <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>
          <div>
            <Label htmlFor="intent">Intent (markdown)</Label>
            <Textarea
              id="intent"
              rows={5}
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
              placeholder={"## Why\n\nWhat are we trying to achieve?"}
              required
            />
          </div>
          <div>
            <Label htmlFor="scope">Scope (optional markdown)</Label>
            <Textarea
              id="scope"
              rows={4}
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              placeholder={"- In scope\n- Out of scope"}
            />
          </div>
          <div>
            <Label htmlFor="ac">Acceptance criteria (markdown)</Label>
            <Textarea
              id="ac"
              rows={5}
              value={acceptanceCriteria}
              onChange={(e) => setAcceptanceCriteria(e.target.value)}
              placeholder={"- [ ] Criteria 1\n- [ ] Criteria 2"}
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="team">Team</Label>
              <Input id="team" value={team} onChange={(e) => setTeam(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="project">Project</Label>
              <Input id="project" value={project} onChange={(e) => setProject(e.target.value)} />
            </div>
          </div>
          {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
          <Button type="submit" disabled={loading}>
            {loading ? "Creating…" : "Create plan"}
          </Button>
        </form>
      </Card>
    </AppShell>
  );
}
