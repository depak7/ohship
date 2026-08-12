"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Button, Card, Input, Label } from "@/components/ui";
import { api, Member, Organization } from "@/lib/api";
import { clearOrgId, getOrgId, setOrgId } from "@/lib/auth";

export default function OrgsPage() {
  const router = useRouter();
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [inviteUrl, setInviteUrl] = useState("");
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [orgId, setLocalOrgId] = useState<string | null>(null);

  async function refresh() {
    const list = await api.listOrgs();
    setOrgs(list);
    const current = getOrgId() || list[0]?.id || null;
    if (current && list.some((o) => o.id === current)) {
      setOrgId(current);
      setLocalOrgId(current);
      setMembers(await api.listMembers(current));
    } else if (list[0]) {
      setOrgId(list[0].id);
      setLocalOrgId(list[0].id);
      setMembers(await api.listMembers(list[0].id));
    } else {
      clearOrgId();
      setLocalOrgId(null);
      setMembers([]);
    }
  }

  useEffect(() => {
    setLocalOrgId(getOrgId());
    refresh().catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  async function createInvite() {
    if (!orgId) return;
    try {
      const invite = await api.createInvite(orgId);
      setInviteUrl(invite.invite_url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create invite");
    }
  }

  const current = orgs.find((o) => o.id === orgId);

  async function handleDelete() {
    if (!orgId || !current) return;
    const ok = window.confirm(
      `Delete organization "${current.name}"?\n\nThis permanently removes all plans, Done history, invites, and memberships. This cannot be undone.`
    );
    if (!ok) return;

    setDeleting(true);
    setError("");
    try {
      await api.deleteOrg(orgId);
      clearOrgId();
      setInviteUrl("");
      const remaining = await api.listOrgs();
      setOrgs(remaining);
      if (remaining.length === 0) {
        setLocalOrgId(null);
        setMembers([]);
        router.push("/orgs/new");
        return;
      }
      setOrgId(remaining[0].id);
      setLocalOrgId(remaining[0].id);
      setMembers(await api.listMembers(remaining[0].id));
      window.location.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete organization");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <AppShell>
      <div className="mb-8 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Organization</h1>
          <p className="mt-2 text-[var(--muted)]">
            Create a workspace, invite teammates, and share every plan.
          </p>
        </div>
        <Link href="/orgs/new">
          <Button>New organization</Button>
        </Link>
      </div>

      {error && <p className="mb-4 text-sm text-[var(--danger)]">{error}</p>}

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">
              {current ? current.name : "No organization selected"}
            </h2>
            {current?.role === "owner" && (
              <button
                type="button"
                aria-label="Delete organization"
                title="Delete organization"
                onClick={handleDelete}
                disabled={deleting}
                className="rounded-lg p-1.5 text-[var(--muted)] transition hover:bg-[var(--danger)]/10 hover:text-[var(--danger)] disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" strokeWidth={1.75} />
              </button>
            )}
          </div>
          {current && (
            <>
              <p className="mb-4 text-sm text-[var(--muted)]">
                slug <code className="rounded bg-black/5 px-1.5 py-0.5">{current.slug}</code>
                {" · "}
                {current.member_count} members
                {" · "}
                {current.role}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button onClick={createInvite}>Create invite link</Button>
              </div>
              {inviteUrl && (
                <div className="mt-4">
                  <Label>Share this link</Label>
                  <Input readOnly value={inviteUrl} onFocus={(e) => e.target.select()} />
                </div>
              )}
            </>
          )}
        </Card>

        <Card>
          <h2 className="mb-4 text-lg font-semibold">Members</h2>
          <div className="space-y-3">
            {members.map((m) => (
              <div key={m.id} className="flex items-center justify-between border-b border-[var(--line)] pb-3 last:border-0">
                <div>
                  <p className="font-medium">{m.name}</p>
                  <p className="text-sm text-[var(--muted)]">{m.email}</p>
                </div>
                <span className="text-xs uppercase tracking-wide text-[var(--muted)]">{m.role}</span>
              </div>
            ))}
            {members.length === 0 && (
              <p className="text-sm text-[var(--muted)]">No members yet.</p>
            )}
          </div>
        </Card>
      </div>

      <div className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          Your organizations
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {orgs.map((o) => (
            <button
              key={o.id}
              className="surface rounded-2xl p-4 text-left hover:bg-white"
              onClick={() => {
                setOrgId(o.id);
                router.refresh();
                window.location.reload();
              }}
            >
              <p className="font-medium">{o.name}</p>
              <p className="text-sm text-[var(--muted)]">
                {o.member_count} members · {o.role}
              </p>
            </button>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
