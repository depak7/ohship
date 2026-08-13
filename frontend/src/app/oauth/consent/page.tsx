"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { getApiUrl, getToken } from "@/lib/auth";
import { Button, Card } from "@/components/ui";

function ConsentInner() {
  const router = useRouter();
  const params = useSearchParams();
  const state = params.get("state") || "";
  const [clientId, setClientId] = useState("");
  const [scopes, setScopes] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(false);

  useEffect(() => {
    if (!state) {
      setError("Missing OAuth state");
      setLoading(false);
      return;
    }
    if (!getToken()) {
      router.replace(`/login?next=${encodeURIComponent(`/oauth/consent?state=${state}`)}`);
      return;
    }
    fetch(`${getApiUrl()}/api/v1/oauth/consent/${state}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
      .then(async (res) => {
        if (!res.ok) throw new Error((await res.json()).detail || "Invalid OAuth request");
        return res.json();
      })
      .then((data) => {
        setClientId(data.client_id);
        setScopes(data.scopes || []);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load consent"))
      .finally(() => setLoading(false));
  }, [state, router]);

  async function approve() {
    setApproving(true);
    setError("");
    try {
      const res = await fetch(`${getApiUrl()}/api/v1/oauth/approve`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${getToken()}`,
        },
        body: JSON.stringify({ state }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Approval failed");
      window.location.href = data.redirect_uri;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approval failed");
      setApproving(false);
    }
  }

  return (
    <div className="grain flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-md">
        <p className="text-sm uppercase tracking-[0.18em] text-[var(--accent)]">MCP OAuth</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          Allow access to Planlog?
        </h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          An MCP client wants to use your Planlog account (same login as the web app).
        </p>

        {loading && <p className="mt-6 text-[var(--muted)]">Loading…</p>}
        {error && <p className="mt-6 text-sm text-[var(--danger)]">{error}</p>}

        {!loading && !error && (
          <div className="mt-6 space-y-4">
            <div className="rounded-xl border border-[var(--line)] bg-white/60 p-4 text-sm">
              <p>
                <span className="text-[var(--muted)]">Client</span>
                <br />
                <span className="font-medium break-all">{clientId || "MCP client"}</span>
              </p>
              <p className="mt-3">
                <span className="text-[var(--muted)]">Scopes</span>
                <br />
                <span className="font-medium">{scopes.join(", ") || "planlog"}</span>
              </p>
            </div>
            <div className="flex gap-3">
              <Button className="flex-1" onClick={approve} disabled={approving}>
                {approving ? "Allowing…" : "Allow"}
              </Button>
              <Link href="/" className="flex-1">
                <Button variant="outline" className="w-full">
                  Cancel
                </Button>
              </Link>
            </div>
            <p className="text-xs text-[var(--muted)]">
              You signed in with email or Google. Agents get a token for your account — no separate API key needed.
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}

export default function OAuthConsentPage() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-[var(--muted)]">Loading…</div>}>
      <ConsentInner />
    </Suspense>
  );
}
