"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";

function publicSiteUrl(): string {
  return (
    process.env.NEXT_PUBLIC_SITE_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "https://planlog.depak.dev"
  ).replace(/\/$/, "");
}

/** App host sends logged-out visitors to planlog.depak.dev; logged-in users to /plans. */
export default function AppIndexRedirect() {
  const router = useRouter();

  useEffect(() => {
    if (getToken()) {
      router.replace("/plans");
      return;
    }
    window.location.replace(publicSiteUrl());
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center text-[var(--muted)]">
      Redirecting…
    </div>
  );
}
