"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { setApiKey, setToken } from "@/lib/auth";
import { Button, Card, Input, Label } from "@/components/ui";

export default function ApiKeyLoginPage() {
  const router = useRouter();
  const [apiKey, setApiKeyInput] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const key = apiKey.trim();
    setToken(key);
    setApiKey(key);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/orgs`,
        { headers: { Authorization: `Bearer ${key}` } }
      );
      if (res.status === 401) {
        setError("Invalid API key");
        return;
      }
      router.push("/plans");
    } catch {
      setError("Could not connect to API");
    }
  }

  return (
    <div className="grain flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-md">
        <h1 className="mb-2 text-2xl font-semibold">API key login</h1>
        <p className="mb-6 text-sm text-[var(--muted)]">
          For agents and bootstrap access. Prefer email login for humans.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="apiKey">API Key</Label>
            <Input
              id="apiKey"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKeyInput(e.target.value)}
              placeholder="dl_..."
              required
            />
          </div>
          {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
          <Button type="submit" className="w-full">
            Continue
          </Button>
        </form>
        <Link href="/login" className="mt-4 inline-block text-sm text-[var(--accent)]">
          ← Back to email login
        </Link>
      </Card>
    </div>
  );
}
