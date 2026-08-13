"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { setApiKey, setToken } from "@/lib/auth";

function CallbackInner() {
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    const token = params.get("token");
    const apiKey = params.get("api_key");
    if (token) {
      setToken(token);
      if (apiKey) setApiKey(apiKey);
      router.replace("/plans");
    } else {
      router.replace("/login");
    }
  }, [params, router]);

  return (
    <div className="flex min-h-screen items-center justify-center text-[var(--muted)]">
      Completing sign-in…
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center text-[var(--muted)]">
          Completing sign-in…
        </div>
      }
    >
      <CallbackInner />
    </Suspense>
  );
}
