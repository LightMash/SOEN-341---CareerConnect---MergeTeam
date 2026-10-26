// Recruiter job posting calls (US-04, Task 4.3).
// Kept in its own file instead of api.ts because the job search branch is
// also adding job code at the end of api.ts, and two branches editing the
// same spot would conflict. Can be merged into api.ts once both are in main.

const API_BASE = "http://localhost:5000/api";

// true = sample postings kept in memory (works without the backend).
// Switch to false once the job posting API from Task 4.2 is merged.
const USE_SAMPLE_DATA = true;

export type EmploymentType = "full_time" | "part_time" | "internship";
export type WorkFrom = "on_site" | "remote" | "hybrid";
export type PostingStatus = "open" | "closed";

// Same field names as the jobs table (models/job.py) and the Job type
// the job search page uses.
export interface JobPosting {
  id: number;
  recruiter_id: number;
  title: string;
  company: string;
  location: string;
  description: string;
  category: string;
  employment_type: EmploymentType;
  work_from: WorkFrom;
  deadline: string | null; // "YYYY-MM-DD"
  status: PostingStatus;
  posted_at: string;
}

// What the form sends when creating or editing a posting.
export type JobPostingInput = Omit<JobPosting, "id" | "recruiter_id" | "status" | "posted_at">;

export const EMPLOYMENT_LABELS: Record<EmploymentType, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  internship: "Internship",
};

export const WORK_FROM_LABELS: Record<WorkFrom, string> = {
  on_site: "On-site",
  remote: "Remote",
  hybrid: "Hybrid",
};

async function send<T>(path: string, token: string, method = "GET", body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    // FastAPI sends {"detail": "..."}; for validation errors detail is a list
    const detail = typeof data.detail === "string" ? data.detail : null;
    throw new Error(detail || "Something went wrong. Try again.");
  }

  return data as T;
}

export function listMyPostings(token: string): Promise<JobPosting[]> {
  if (USE_SAMPLE_DATA) return sample.list();
  return send<JobPosting[]>("/jobs/mine", token);
}

export function createPosting(input: JobPostingInput, token: string): Promise<JobPosting> {
  if (USE_SAMPLE_DATA) return sample.create(input);
  return send<JobPosting>("/jobs", token, "POST", input);
}

export function updatePosting(id: number, input: JobPostingInput, token: string): Promise<JobPosting> {
  if (USE_SAMPLE_DATA) return sample.update(id, input);
  return send<JobPosting>(`/jobs/${id}`, token, "PUT", input);
}

export function setPostingStatus(id: number, status: PostingStatus, token: string): Promise<JobPosting> {
  if (USE_SAMPLE_DATA) return sample.setStatus(id, status);
  return send<JobPosting>(`/jobs/${id}/status`, token, "PATCH", { status });
}

/* ---------- Sample data (only used while USE_SAMPLE_DATA is true) ---------- */

const wait = (ms = 300) => new Promise((resolve) => setTimeout(resolve, ms));

let sampleStore: JobPosting[] = [
  {
    id: 1,
    recruiter_id: 1,
    title: "Software Engineering Intern",
    company: "Northbridge Systems",
    location: "Toronto, ON",
    description: "Join our backend team for a 4-month internship working on REST APIs and database optimization.",
    category: "Software Development",
    employment_type: "internship",
    work_from: "on_site",
    deadline: "2026-11-15",
    status: "open",
    posted_at: "2026-10-18T14:00:00",
  },
  {
    id: 2,
    recruiter_id: 1,
    title: "QA Tester",
    company: "Northbridge Systems",
    location: "Montreal, QC",
    description: "Write and run test plans for our web apps.",
    category: "Software Development",
    employment_type: "part_time",
    work_from: "hybrid",
    deadline: null,
    status: "closed",
    posted_at: "2026-09-30T10:00:00",
  },
];
let nextSampleId = 3;

const sample = {
  async list() {
    await wait();
    return [...sampleStore];
  },
  async create(input: JobPostingInput) {
    await wait();
    const posting: JobPosting = {
      ...input,
      id: nextSampleId++,
      recruiter_id: 1,
      status: "open",
      posted_at: new Date().toISOString(),
    };
    sampleStore = [posting, ...sampleStore];
    return posting;
  },
  async update(id: number, input: JobPostingInput) {
    await wait();
    const existing = sampleStore.find((p) => p.id === id);
    if (!existing) throw new Error("Posting not found.");
    const updated = { ...existing, ...input };
    sampleStore = sampleStore.map((p) => (p.id === id ? updated : p));
    return updated;
  },
  async setStatus(id: number, status: PostingStatus) {
    await wait();
    const existing = sampleStore.find((p) => p.id === id);
    if (!existing) throw new Error("Posting not found.");
    const updated = { ...existing, status };
    sampleStore = sampleStore.map((p) => (p.id === id ? updated : p));
    return updated;
  },
};