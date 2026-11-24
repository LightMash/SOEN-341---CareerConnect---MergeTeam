// Calls for the qualification matching / standing feature (backend/matching/router.py).
// Same request pattern as postingsApi.ts; kept in this folder so the whole
// feature lives in one place.

const API_BASE = "http://localhost:5000/api/matching";

export const CATEGORIES = ["degree", "license", "certification", "language", "skill"] as const;
export type Category = (typeof CATEGORIES)[number];

export const CATEGORY_LABELS: Record<Category, string> = {
  degree: "Degree",
  license: "Licence",
  certification: "Certification",
  language: "Language",
  skill: "Skill",
};

// Matches QualificationOut in backend/matching/schemas.py.
export interface Qualification {
  key: string;
  name: string;
  category: Category;
  field: string | null;
  rank: number | null;
  custom: boolean;
}

export interface SearchResult extends Qualification {
  matched_alias: string;
}

export interface CustomQualification extends Qualification {
  existing: boolean; // true when an existing entry was returned instead of a new one
}

export type QualificationSource = "manual" | "resume_scan" | "reviewer_suggestion";

export interface SeekerQualification extends Qualification {
  source: QualificationSource;
}

export interface Requirement extends Qualification {
  is_required: boolean;
  weight: number; // 1-3, only meaningful for bonus items
}

export interface RequirementInput {
  key: string;
  is_required: boolean;
  weight: number;
}

export type RequirementStatus = "met" | "missing" | "bonus_missing" | "possible";

export interface RequirementResult {
  key: string;
  name: string;
  category: Category;
  is_required: boolean;
  weight: number;
  status: RequirementStatus;
  exceeds: boolean;
  possible_name: string | null;
}

export interface MatchResult {
  listing_id: number;
  qualified: boolean;
  requirements: RequirementResult[];
}

export type CandidateState = "found" | "in_progress" | "questionable" | "suggested";

export interface Candidate {
  key: string;
  name: string;
  category: Category;
  source: "scan" | "reviewer";
  state: CandidateState;
  reason: string | null;
  snippet: string;
  already_added: boolean;
}

export interface UnresolvedItem {
  category: Category | null;
  name: string;
  field: string | null;
}

export interface ExtractResult {
  candidates: Candidate[];
  unresolved: UnresolvedItem[];
  message: string | null;
  reviewer_enabled: boolean;
}

export interface BreakdownRow {
  key: string;
  name: string;
  weight: number;
  has: boolean;
  share: number | null;
  highlight: string | null;
}

export interface Suggestion {
  key: string;
  name: string;
  current: number;
  new: number;
  improvement: number;
}

// Matches StandingOut in backend/matching/schemas.py.
export interface Standing {
  status: "percentile" | "fraction" | "equal_on_paper" | "not_qualified";
  label: string | null;
  percentile: number | null;
  fraction: number | null;
  score: number | null;
  max_score: number | null;
  pool_size: number;
  other_applicants: number;
  as_of: string;
  message: string | null;
  breakdown: BreakdownRow[];
  suggestions: Suggestion[];
  missing: { key: string; name: string; status: string; possible_name: string | null }[];
  profile_nudge: string | null;
  note: string;
}

function errorMessage(status: number, data: { detail?: unknown }): string {
  if (status === 401) return "Your session expired. Log in again.";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((d: { msg?: string }) => (d.msg ?? "Invalid value").replace(/^Value error, /, ""))
      .join(". ");
  }
  return "Something went wrong. Try again.";
}

async function send<T>(path: string, token: string, method = "GET", body?: unknown): Promise<T> {
  let res: Response;
  const isForm = body instanceof FormData;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        // FormData sets its own multipart Content-Type (with the boundary).
        ...(body !== undefined && !isForm ? { "Content-Type": "application/json" } : {}),
      },
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    });
  } catch {
    throw new Error("Couldn't reach the server. Check that the backend is running.");
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(errorMessage(res.status, data));
  return data as T;
}

export function searchQualifications(q: string, category: Category | "", token: string): Promise<SearchResult[]> {
  const params = new URLSearchParams({ q });
  if (category) params.append("category", category);
  return send<SearchResult[]>(`/qualifications/search?${params}`, token);
}

export function createCustomQualification(
  category: Category,
  name: string,
  token: string
): Promise<CustomQualification> {
  return send<CustomQualification>("/qualifications/custom", token, "POST", { category, name });
}

export function getMyQualifications(token: string): Promise<SeekerQualification[]> {
  return send<SeekerQualification[]>("/me/qualifications", token);
}

export function saveMyQualifications(
  items: { key: string; source: QualificationSource }[],
  token: string
): Promise<SeekerQualification[]> {
  return send<SeekerQualification[]>("/me/qualifications", token, "PUT", { qualifications: items });
}

export function claimQualification(key: string, token: string): Promise<SeekerQualification[]> {
  return send<SeekerQualification[]>(`/me/qualifications/claim/${encodeURIComponent(key)}`, token, "POST");
}

export function extractFromResume(source: File | number, token: string): Promise<ExtractResult> {
  const form = new FormData();
  if (typeof source === "number") form.append("resume_id", String(source));
  else form.append("file", source);
  return send<ExtractResult>("/me/qualifications/extract", token, "POST", form);
}

export function getReviewerStatus(token: string): Promise<{ enabled: boolean }> {
  return send<{ enabled: boolean }>("/reviewer", token);
}

export function getRequirements(jobId: number, token: string): Promise<Requirement[]> {
  return send<Requirement[]>(`/listings/${jobId}/requirements`, token);
}

export function saveRequirements(jobId: number, items: RequirementInput[], token: string): Promise<Requirement[]> {
  return send<Requirement[]>(`/listings/${jobId}/requirements`, token, "PUT", { requirements: items });
}

export const MATCH_BATCH_SIZE = 100;

// POST /match takes at most 100 ids, so longer lists go in batches.
export async function matchListings(ids: number[], token: string): Promise<MatchResult[]> {
  const results: MatchResult[] = [];
  for (let i = 0; i < ids.length; i += MATCH_BATCH_SIZE) {
    const batch = ids.slice(i, i + MATCH_BATCH_SIZE);
    results.push(...(await send<MatchResult[]>("/match", token, "POST", batch)));
  }
  return results;
}

export function getStanding(jobId: number, token: string): Promise<Standing> {
  return send<Standing>(`/listings/${jobId}/standing`, token);
}
