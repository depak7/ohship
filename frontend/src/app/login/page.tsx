"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, googleStartUrl } from "@/lib/api";
import { getToken, setApiKey, setToken } from "@/lib/auth";
import { Button, Card, Input, Label } from "@/components/ui";

function LoginInner() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/plans";
  const [mode, setMode] = useState<"login" | "signup">(
    () => (params.get("mode") === "signup" ? "signup" : "login")
  );
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);

  useEffect(() => {
    if (params.get("mode") === "signup") setMode("signup");
  }, [params]);

  useEffect(() => {
    if (getToken()) router.replace(next);
    api.googleConfig().then((c) => setGoogleEnabled(c.enabled)).catch(() => setGoogleEnabled(false));
  }, [router, next]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res =
        mode === "login"
          ? await api.login({ email, password })
          : await api.signup({ name, email, password });
      setToken(res.access_token);
      if (res.api_key) setApiKey(res.api_key);
      router.push(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grain flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent)]">Planlog</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">
            Plans written in markdown.
          </h1>
          <p className="mt-2 text-[var(--muted)]">
            Approve them. Ship them. Keep Done as permanent history.
          </p>
        </div>

        <Card>
          <div className="mb-5 flex gap-2 rounded-xl bg-black/5 p-1">
            <button
              type="button"
              className={`flex-1 rounded-lg px-3 py-2 text-sm ${mode === "login" ? "bg-white shadow-sm" : ""}`}
              onClick={() => setMode("login")}
            >
              Sign in
            </button>
            <button
              type="button"
              className={`flex-1 rounded-lg px-3 py-2 text-sm ${mode === "signup" ? "bg-white shadow-sm" : ""}`}
              onClick={() => setMode("signup")}
            >
              Create account
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "signup" && (
              <div>
                <Label htmlFor="name">Name</Label>
                <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required />
              </div>
            )}
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                required
              />
            </div>
            {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
            </Button>
          </form>

          <div className="my-5 flex items-center gap-3 text-xs text-[var(--muted)]">
            <div className="h-px flex-1 bg-[var(--line)]" />
            or
            <div className="h-px flex-1 bg-[var(--line)]" />
          </div>

          {googleEnabled ? (
            <a href={googleStartUrl()}>
              <Button type="button" variant="outline" className="w-full">
                Continue with Google
              </Button>
            </a>
          ) : (
            <p className="text-center text-xs text-[var(--muted)]">
              Google login available when{" "}
              <code className="rounded bg-black/5 px-1">GOOGLE_CLIENT_ID</code> is configured.
            </p>
          )}
        </Card>

        <p className="mt-6 text-center text-xs text-[var(--muted)]">
          MCP agents can use the same login via OAuth — or an API key.
        </p>
        <p className="mt-2 text-center text-xs">
          <Link href="/login/api-key" className="text-[var(--accent)] underline">
            Use an API key instead
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-[var(--muted)]">Loading…</div>}>
      <LoginInner />
    </Suspense>
  );
}
