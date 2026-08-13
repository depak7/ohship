"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, Organization, UserBrief } from "@/lib/api";
import {
  clearProject,
  clearSession,
  getOrgId,
  getProject,
  getToken,
  setOrgId,
  setProject,
} from "@/lib/auth";
import { Button, Select } from "@/components/ui";

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<UserBrief | null>(null);
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [orgId, setLocalOrgId] = useState<string | null>(null);
  const [projects, setProjects] = useState<string[]>([]);
  const [activeProject, setActiveProject] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    (async () => {
      try {
        const [me, orgList] = await Promise.all([api.me(), api.listOrgs()]);
        setUser(me);
        setOrgs(orgList);
        const saved = getOrgId();
        const selected =
          (saved && orgList.find((o) => o.id === saved)?.id) || orgList[0]?.id || null;
        if (selected) {
          setOrgId(selected);
          setLocalOrgId(selected);
          const names = await api.listProjects();
          setProjects(names);
        } else if (!pathname.startsWith("/orgs")) {
          router.replace("/orgs/new");
        }
        setActiveProject(getProject() || "");
      } catch {
        clearSession();
        router.replace("/login");
      } finally {
        setLoading(false);
      }
    })();
  }, [router, pathname]);

  useEffect(() => {
    function onProjectChange() {
      setActiveProject(getProject() || "");
    }
    window.addEventListener("ohship-project-change", onProjectChange);
    return () => window.removeEventListener("ohship-project-change", onProjectChange);
  }, []);

  function handleProjectChange(value: string) {
    if (value) setProject(value);
    else clearProject();
    setActiveProject(value);
    window.dispatchEvent(new Event("ohship-project-change"));
    if (pathname !== "/") router.push("/");
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-[var(--muted)]">
        Loading workspace…
      </div>
    );
  }

  const currentOrg = orgs.find((o) => o.id === orgId);

  return (
    <div className="grain min-h-screen">
      <header className="sticky top-0 z-20 border-b border-[var(--line)] bg-[color-mix(in_srgb,var(--bg)_88%,white)] backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-6">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              OhShip
            </Link>
            <nav className="hidden items-center gap-4 text-sm text-[var(--muted)] sm:flex">
              <Link href="/" className={pathname === "/" ? "text-[var(--ink)]" : ""}>
                Plans
              </Link>
              <Link
                href="/orgs"
                className={pathname.startsWith("/orgs") ? "text-[var(--ink)]" : ""}
              >
                Organization
              </Link>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            {orgs.length > 0 && (
              <Select
                value={orgId || ""}
                onChange={async (e) => {
                  setOrgId(e.target.value);
                  setLocalOrgId(e.target.value);
                  clearProject();
                  setActiveProject("");
                  const names = await api.listProjects();
                  setProjects(names);
                  router.refresh();
                  if (pathname !== "/") router.push("/");
                  else window.location.reload();
                }}
              >
                {orgs.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
              </Select>
            )}
            <span className="hidden text-sm text-[var(--muted)] md:inline">
              {user?.name}
            </span>
            <Button
              variant="outline"
              onClick={() => {
                clearSession();
                router.push("/login");
              }}
            >
              Sign out
            </Button>
          </div>
        </div>
        {currentOrg && (
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 pb-3 text-xs text-[var(--muted)]">
            <span>
              Org: <span className="font-medium text-[var(--ink)]">{currentOrg.name}</span>
            </span>
            {projects.length > 0 && (
              <>
                <span aria-hidden>·</span>
                <label className="flex items-center gap-2">
                  Project
                  <Select
                    className="text-xs"
                    value={activeProject}
                    onChange={(e) => handleProjectChange(e.target.value)}
                  >
                    <option value="">All projects</option>
                    {projects.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </Select>
                </label>
              </>
            )}
            <span aria-hidden>·</span>
            <span>Plans grouped by project; team is optional metadata.</span>
          </div>
        )}
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}
