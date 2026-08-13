"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";

export function LandingRedirect() {
  const router = useRouter();

  useEffect(() => {
    if (getToken()) router.replace("/plans");
  }, [router]);

  return null;
}
