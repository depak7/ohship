"use client";

import { useState } from "react";
import { Button } from "@/components/ui";
import { api, PlanDetail, PlanVisibility } from "@/lib/api";

export function ShareSidebar({
  plan,
  disabled,
  onUpdate,
}: {
  plan: PlanDetail;
  disabled?: boolean;
  onUpdate: (plan: PlanDetail) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  async function setVisibility(visibility: PlanVisibility, rotate = false) {
    setLoading(true);
    setError("");
    try {
      onUpdate(await api.setPlanShare(plan.id, { visibility, rotate }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update sharing");
    } finally {
      setLoading(false);
    }
  }

  async function copyLink() {
    if (!plan.share_url) return;
    await navigator.clipboard.writeText(plan.share_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const isAnyone = plan.visibility === "anyone";

  return (
    <aside className="surface rounded-2xl p-5">
      <h2 className="mb-3 text-sm font-semibold">Share</h2>

      <div className="space-y-2">
        <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-[var(--line)] p-3 text-sm hover:bg-black/[0.02]">
          <input
            type="radio"
            name={`share-${plan.id}`}
            checked={!isAnyone}
            disabled={disabled || loading}
            onChange={() => setVisibility("team")}
            className="mt-0.5"
          />
          <span>
            <span className="block font-medium">Team</span>
            <span className="text-xs text-[var(--muted)]">Org members with login</span>
          </span>
        </label>

        <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-[var(--line)] p-3 text-sm hover:bg-black/[0.02]">
          <input
            type="radio"
            name={`share-${plan.id}`}
            checked={isAnyone}
            disabled={disabled || loading}
            onChange={() => setVisibility("anyone")}
            className="mt-0.5"
          />
          <span>
            <span className="block font-medium">Anyone with link</span>
            <span className="text-xs text-[var(--muted)]">View without login</span>
          </span>
        </label>
      </div>

      {isAnyone && plan.share_url && (
        <div className="mt-4 space-y-2 border-t border-[var(--line)] pt-4">
          <p className="break-all rounded-lg bg-black/[0.03] px-3 py-2 font-mono text-xs text-[var(--muted)]">
            {plan.share_url}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" className="text-xs" disabled={loading} onClick={copyLink}>
              {copied ? "Copied" : "Copy link"}
            </Button>
            <Button
              variant="outline"
              className="text-xs"
              disabled={loading}
              onClick={() => setVisibility("anyone", true)}
            >
              Reset link
            </Button>
          </div>
        </div>
      )}

      {error && <p className="mt-3 text-xs text-[var(--danger)]">{error}</p>}
    </aside>
  );
}

export async function ensureAnyoneLink(planId: string): Promise<string> {
  const detail = await api.getPlan(planId);
  if (detail.share_url && detail.visibility === "anyone") {
    return detail.share_url;
  }
  const updated = await api.setPlanShare(planId, { visibility: "anyone" });
  if (!updated.share_url) {
    throw new Error("Could not create share link");
  }
  return updated.share_url;
}
