"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { getToken, setOrgId } from "@/lib/auth";
import { Button, Card } from "@/components/ui";

function InviteInner() {
  const params = useParams();
  const router = useRouter();
  const token = params.token as string;
  const [preview, setPreview] = useState<{
    organization_name: string;
    valid: boolean;
  } | null>(null);
  const [error, setError] = useState("");
  const [joining, setJoining] = useState(false);

  useEffect(() => {
    api
      .previewInvite(token)
      .then(setPreview)
      .catch((e) => setError(e instanceof Error ? e.message : "Invalid invite"));
  }, [token]);

  async function join() {
    if (!getToken()) {
      router.push(`/login?next=/invite/${token}`);
      return;
    }
    setJoining(true);
    try {
      const org = await api.joinInvite(token);
      setOrgId(org.id);
      router.push("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not join");
    } finally {
      setJoining(false);
    }
  }

  return (
    <div className="grain flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-md text-center">
        <p className="text-sm uppercase tracking-[0.18em] text-[var(--accent)]">Invite</p>
        {preview ? (
          <>
            <h1 className="mt-3 text-2xl font-semibold">
              Join {preview.organization_name}
            </h1>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Everyone in the org can see all plans and Done history.
            </p>
            {!preview.valid && (
              <p className="mt-4 text-sm text-[var(--danger)]">This invite has expired.</p>
            )}
            {error && <p className="mt-4 text-sm text-[var(--danger)]">{error}</p>}
            <div className="mt-6 flex justify-center gap-3">
              <Button onClick={join} disabled={!preview.valid || joining}>
                {joining ? "Joining…" : getToken() ? "Join organization" : "Sign in to join"}
              </Button>
              <Link href="/">
                <Button variant="outline">Cancel</Button>
              </Link>
            </div>
          </>
        ) : (
          <p className="mt-4 text-[var(--muted)]">{error || "Loading invite…"}</p>
        )}
      </Card>
    </div>
  );
}

export default function InvitePage() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-[var(--muted)]">Loading…</div>}>
      <InviteInner />
    </Suspense>
  );
}
