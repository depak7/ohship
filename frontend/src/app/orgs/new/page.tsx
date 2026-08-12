"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Button, Card, Input, Label } from "@/components/ui";
import { api } from "@/lib/api";
import { setOrgId } from "@/lib/auth";

export default function NewOrgPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const org = await api.createOrg(name);
      setOrgId(org.id);
      router.push("/orgs");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create organization");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-xl">
        <h1 className="mb-2 text-3xl font-semibold tracking-tight">Create organization</h1>
        <p className="mb-6 text-[var(--muted)]">
          A shared workspace where everyone can see all plans and Done history.
        </p>
        <Card>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="name">Organization name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Acme Engineering"
                required
              />
            </div>
            {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
            <Button type="submit" disabled={loading}>
              {loading ? "Creating…" : "Create organization"}
            </Button>
          </form>
        </Card>
      </div>
    </AppShell>
  );
}
