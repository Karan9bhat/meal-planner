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
// In production set NEXT_PUBLIC_API_URL, and add this site's origin to the backend's CORS_ORIGINS.
const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

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
export const getOptions = () => request<Options>(`${API_URL}/api/options`);
export const getTargets = (basics: Basics, signal?: AbortSignal) => request<Targets>(`${API_URL}/api/targets`, post(basics, signal));
export const resolveRegion = (location: string) =>
  request<RegionResolution>(`${API_URL}/api/region/resolve`, post({ location }));
export const regionStatus = (key: string) => request<RegionResolution>(`${API_URL}/api/region/${encodeURIComponent(key)}`);
export const createPlan = (profile: Profile) => request<PlanResponse>(`${API_URL}/api/plan`, post(profile));
export const checkPlan = (plan: Plan, targets: Targets, daily_budget: number) =>
  request<DayCheck[]>(`${API_URL}/api/plan/check`, post({ plan, targets, daily_budget }));

// ---- Next.js agent routes (Mastra) ----
export const analyzeDay = (body: { description: string; answers?: string; profile: Profile }) =>
  request<IntakeResult>("/api/agent/intake", post(body));
export const analyzePantry = (body: { text: string; profile: Profile }) => request<PantryResult>("/api/agent/pantry", post(body));
