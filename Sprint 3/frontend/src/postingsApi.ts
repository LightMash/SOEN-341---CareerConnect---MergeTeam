// Recruiter job posting calls (US-04, Task 4.3).
// Kept in its own file instead of api.ts because teammates are also adding
// job code to api.ts. Field names and routes match backend/schemas/job.py
// and backend/routers/job.py.

const API_BASE = "http://localhost:5000/api";

// Same list as JOB_TYPES in backend/models/job.py (exact spelling matters).
export const JOB_TYPES = ["Full-time", "Part-time", "Internship", "Contract"] as const;
export type JobType = (typeof JOB_TYPES)[number];

// Limits enforced by the backend (schemas/job.py).
export const MAX_DESCRIPTION = 5000;
export const MAX_SALARY = 10_000_000;

// Matches JobOut in backend/schemas/job.py.
export interface JobPosting {
  id: number;
  recruiter_id: number;
  title: string;
  company: string;
  location: string;
  job_type: JobType;
  category: string;
  description: string;
  salary_min: number | null;
  salary_max: number | null;
  is_open: boolean;
  created_at: string;
  updated_at: string;
}

// Matches JobIn: exactly the fields POST /api/jobs and PUT /api/jobs/{id}
// accept. The backend rejects any extra field (extra="forbid").
export type JobPostingInput = Pick<
  JobPosting,
  "title" | "company" | "location" | "job_type" | "category" | "description" | "salary_min" | "salary_max"
>;

// Turns any backend error into one readable sentence.
function errorMessage(status: number, data: { detail?: unknown }): string {
  if (status === 401) return "Your session expired. Log in again.";
  if (typeof data.detail === "string") return data.detail;

  // Validation errors (422) come as a list like
  // [{ loc: ["body", "salary_max"], msg: "..." }, ...]
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((d: { loc?: (string | number)[]; msg?: string }) => {
        const field = (d.loc ?? []).slice(1).join(" ").replace(/_/g, " ");
        const msg = (d.msg ?? "Invalid value").replace(/^Value error, /, "");
        return field ? `${field}: ${msg}` : msg;
      })
      .join(". ");
  }

  return "Something went wrong. Try again.";
}

async function send<T>(path: string, token: string, method = "GET", body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Couldn't reach the server. Check that the backend is running.");
  }

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(errorMessage(res.status, data));
  }

  return data as T;
}

export function listMyPostings(token: string): Promise<JobPosting[]> {
  return send<JobPosting[]>("/jobs/mine", token);
}

export function createPosting(input: JobPostingInput, token: string): Promise<JobPosting> {
  return send<JobPosting>("/jobs", token, "POST", input);
}

export function updatePosting(id: number, input: JobPostingInput, token: string): Promise<JobPosting> {
  return send<JobPosting>(`/jobs/${id}`, token, "PUT", input);
}

export function closePosting(id: number, token: string): Promise<JobPosting> {
  return send<JobPosting>(`/jobs/${id}/close`, token, "POST");
}

export function reopenPosting(id: number, token: string): Promise<JobPosting> {
  return send<JobPosting>(`/jobs/${id}/reopen`, token, "POST");
}