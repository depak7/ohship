import { getApiUrl, getOrgId, getToken } from "./auth";

export type PlanVisibility = "team" | "anyone";

export type PlanStatus =
  | "draft"
  | "in_review"
  | "changes_requested"
  | "approved"
  | "in_progress"
  | "done";

export interface UserBrief {
  id: string;
  name: string;
  email: string;
  avatar_url?: string | null;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  role: "owner" | "member";
  created_at: string;
  member_count: number;
}

export interface Member {
  id: string;
  name: string;
  email: string;
  avatar_url?: string | null;
  role: "owner" | "member";
  joined_at: string;
}

export interface DoneLink {
  type: string;
  url: string;
  label: string;
}

export interface PlanSummary {
  id: string;
  organization_id: string;
  title: string;
  status: PlanStatus;
  owner: UserBrief;
  team: string | null;
  project: string | null;
  claimed_by: UserBrief | null;
  reviewers?: UserBrief[];
  visibility?: PlanVisibility;
  share_url?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Suggestion {
  id: string;
  plan_id: string;
  author: UserBrief;
  content: string;
  created_at: string;
}

export type CriterionStatus = "met" | "changed" | "dropped" | "unreported" | "extra";

export interface CriterionOutcome {
  criterion: string;
  status: CriterionStatus;
  note?: string | null;
}

export interface DoneRecord {
  id: string;
  plan_id: string;
  summary: string;
  links: DoneLink[];
  residual_notes: string | null;
  handoff_notes?: string | null;
  reconciliation?: CriterionOutcome[];
  posted_by: UserBrief;
  posted_at: string;
  handoff_to?: UserBrief[];
}

export interface PlanDetail extends PlanSummary {
  intent: string;
  scope: string | null;
  acceptance_criteria: string;
  approved_at: string | null;
  approved_by: UserBrief | null;
  approval_kind?: "peer" | "self" | "on_ship" | null;
  suggestions: Suggestion[];
  done: DoneRecord | null;
  markdown: string;
  agent_prompt?: string;
  notifyees?: UserBrief[];
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserBrief & { created_at?: string };
  api_key?: string | null;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  auth = true
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (auth) {
    const token = getToken();
    if (!token) throw new ApiError("Not authenticated", 401);
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${getApiUrl()}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), res.status);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export const api = {
  signup: (body: { name: string; email: string; password: string }) =>
    request<AuthResponse>("/api/v1/auth/signup", { method: "POST", body: JSON.stringify(body) }, false),
  login: (body: { email: string; password: string }) =>
    request<AuthResponse>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(body) }, false),
  me: () => request<UserBrief & { created_at: string }>("/api/v1/auth/me"),
  googleConfig: () =>
    request<{ enabled: boolean; client_id?: string }>("/api/v1/auth/google/config", {}, false),
  rotateApiKey: () =>
    request<UserBrief & { api_key: string }>("/api/v1/auth/api-key", { method: "POST" }),

  listOrgs: () => request<Organization[]>("/api/v1/orgs"),
  createOrg: (name: string) =>
    request<Organization>("/api/v1/orgs", { method: "POST", body: JSON.stringify({ name }) }),
  deleteOrg: (orgId: string) =>
    request<void>(`/api/v1/orgs/${orgId}`, { method: "DELETE" }),
  listMembers: (orgId: string) => request<Member[]>(`/api/v1/orgs/${orgId}/members`),
  createInvite: (orgId: string) =>
    request<{ token: string; invite_url: string; organization_name: string }>(
      `/api/v1/orgs/${orgId}/invites`,
      { method: "POST" }
    ),
  previewInvite: (token: string) =>
    request<{
      organization_id: string;
      organization_name: string;
      organization_slug: string;
      valid: boolean;
    }>(`/api/v1/orgs/invites/${token}`, {}, false),
  joinInvite: (token: string) =>
    request<Organization>(`/api/v1/orgs/invites/${token}/join`, { method: "POST" }),

  listPlans: (params?: Record<string, string>) => {
    const orgId = params?.organization_id || getOrgId();
    if (!orgId) throw new ApiError("No organization selected", 400);
    const query = new URLSearchParams({ organization_id: orgId, ...params });
    query.delete("organization_id");
    query.set("organization_id", orgId);
    return request<{ plans: PlanSummary[]; total: number }>(`/api/v1/plans?${query}`);
  },
  listProjects: () => {
    const orgId = getOrgId();
    if (!orgId) throw new ApiError("No organization selected", 400);
    return request<string[]>(`/api/v1/plans/projects?organization_id=${orgId}`);
  },
  getPlan: (id: string) => request<PlanDetail>(`/api/v1/plans/${id}`),
  deletePlan: (id: string) =>
    request<void>(`/api/v1/plans/${id}`, { method: "DELETE" }),
  createPlan: (body: {
    title: string;
    intent: string;
    acceptance_criteria: string;
    scope?: string;
    team?: string;
    project: string;
    organization_id: string;
  }) =>
    request<PlanDetail>("/api/v1/plans", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updatePlan: (id: string, body: Record<string, string | undefined>) =>
    request<PlanDetail>(`/api/v1/plans/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  submitPlan: (id: string, reviewerIds?: string[]) =>
    request<PlanDetail>(`/api/v1/plans/${id}/submit`, {
      method: "POST",
      body: JSON.stringify({ reviewer_ids: reviewerIds || [] }),
    }),
  requestReviewers: (id: string, reviewerIds: string[]) =>
    request<PlanDetail>(`/api/v1/plans/${id}/reviewers`, {
      method: "POST",
      body: JSON.stringify({ reviewer_ids: reviewerIds }),
    }),
  requestNotifyees: (id: string, notifyIds: string[]) =>
    request<PlanDetail>(`/api/v1/plans/${id}/notifyees`, {
      method: "POST",
      body: JSON.stringify({ notify_ids: notifyIds }),
    }),
  approvePlan: (id: string) =>
    request<PlanDetail>(`/api/v1/plans/${id}/approve`, { method: "POST" }),
  requestChanges: (id: string, content?: string) =>
    request<PlanDetail>(`/api/v1/plans/${id}/request-changes`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
  claimPlan: (id: string) =>
    request<PlanDetail>(`/api/v1/plans/${id}/claim`, { method: "POST" }),
  postDone: (
    id: string,
    body: {
      summary: string;
      links: DoneLink[];
      residual_notes?: string;
      handoff_notes?: string;
      handoff_to?: string[];
      reconciliation?: CriterionOutcome[];
    }
  ) =>
    request<PlanDetail>(`/api/v1/plans/${id}/done`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  setPlanShare: (
    id: string,
    body: { visibility: PlanVisibility; rotate?: boolean }
  ) =>
    request<PlanDetail>(`/api/v1/plans/${id}/share`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getPublicPlan: (token: string) =>
    request<{
      title: string;
      status: PlanStatus;
      owner_name: string;
      markdown: string;
      done: {
        summary: string;
        links: DoneLink[];
        residual_notes: string | null;
        posted_by_name: string;
        posted_at: string;
      } | null;
    }>(`/api/v1/public/plans/${token}`, {}, false),
  addSuggestion: (id: string, content: string) =>
    request<PlanDetail>(`/api/v1/plans/${id}/suggestions`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
};

export const STATUS_LABELS: Record<PlanStatus, string> = {
  draft: "Draft",
  in_review: "In Review",
  changes_requested: "Changes Requested",
  approved: "Approved",
  in_progress: "In Progress",
  done: "Done",
};

export function googleStartUrl(): string {
  return `${getApiUrl()}/api/v1/auth/google/start`;
}

/** Mirrors parse_criteria in backend services/helpers.py — the backend is the source of
 *  truth, this only drives the Done form's per-criterion controls. */
export function parseCriteria(acceptanceCriteria: string): string[] {
  const items = (acceptanceCriteria || "")
    .split("\n")
    .map((line) => line.match(/^\s*(?:[-*+]\s+(?:\[[ xX]\]\s*)?|\d+[.)]\s+)(.+?)\s*$/))
    .filter((m): m is RegExpMatchArray => Boolean(m))
    .map((m) => m[1].trim())
    .filter(Boolean);
  if (items.length) return items;
  const blob = (acceptanceCriteria || "").trim();
  return blob ? [blob] : [];
}
