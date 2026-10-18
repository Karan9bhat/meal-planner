import type {
  Basics,
  DayCheck,
  IntakeResult,
  Options,
  PantryResult,
  Plan,
  PlanResponse,
  Profile,
  RegionResolution,
  Targets,
} from "./types";

// The browser calls FastAPI directly (plan generation can outlast proxy timeouts).
// Where it lives comes from this site's own /api/config at runtime (BACKEND_URL on the web service), so moving the
// backend never needs a rebuild. Add this site's origin to the backend's CORS settings.
let apiBase: Promise<string> | null = null;

export function getApiBase(): Promise<string> {
  apiBase ??= fetch("/api/config")
    .then((r) => r.json() as Promise<{ apiUrl: string }>)
    .then((c) => c.apiUrl)
    .catch(() => "http://localhost:8000");
  return apiBase;
}

const api = async (path: string) => `${await getApiBase()}${path}`;

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (typeof body.error === "string") message = body.error;
      else if (Array.isArray(body.detail)) message = "Some answers look invalid — please review the form.";
    } catch {
      /* non-JSON error body */
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

const post = (body: unknown, signal?: AbortSignal): RequestInit => ({ method: "POST", body: JSON.stringify(body), signal });

// ---- FastAPI (deterministic engine + knowledge base + planner) ----
export const getOptions = async () => request<Options>(await api("/api/options"));
export const getTargets = async (basics: Basics, signal?: AbortSignal) =>
  request<Targets>(await api("/api/targets"), post(basics, signal));
export const resolveRegion = async (location: string) =>
  request<RegionResolution>(await api("/api/region/resolve"), post({ location }));
export const regionStatus = async (key: string) => request<RegionResolution>(await api(`/api/region/${encodeURIComponent(key)}`));
export const createPlan = async (profile: Profile) => request<PlanResponse>(await api("/api/plan"), post(profile));
export const checkPlan = async (plan: Plan, targets: Targets, daily_budget: number) =>
  request<DayCheck[]>(await api("/api/plan/check"), post({ plan, targets, daily_budget }));

// ---- Next.js agent routes (Mastra) ----
export const analyzeDay = (body: { description: string; answers?: string; profile: Profile }) =>
  request<IntakeResult>("/api/agent/intake", post(body));
export const analyzePantry = (body: { text: string; profile: Profile }) => request<PantryResult>("/api/agent/pantry", post(body));
