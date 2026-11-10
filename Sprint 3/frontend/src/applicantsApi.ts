const API_BASE = "http://localhost:5000/api";

// Must match the backend's allowed status values exactly.
export const APPLICATION_STATUSES = [
  "Applied",
  "Under Review",
  "Interview",
  "Offered",
  "Rejected",
] as const;

export type ApplicationStatus =
  (typeof APPLICATION_STATUSES)[number];

// Response from GET /jobs/{jobId}/applications
export interface Applicant {
  id: number;
  job_id: number;
  job_title: string;
  company: string;
  applicant_id: number;
  applicant_name: string;
  applicant_email: string;
  resume_id: number | null;
  resume_filename: string | null;
  status: ApplicationStatus;
  applied_at: string;
  updated_at: string;
}

// Response from GET /applications/{id}/history
export interface ApplicationHistoryEntry {
  old_status: ApplicationStatus | null;
  new_status: ApplicationStatus;
  changed_by: number;
  changed_at: string;
}

// Same request pattern as postingsApi.ts.
async function send<T>(
  path: string,
  token: string,
  method = "GET",
  body?: unknown
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body !== undefined
        ? { "Content-Type": "application/json" }
        : {}),
    },
    body: body !== undefined
      ? JSON.stringify(body)
      : undefined,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : "Something went wrong. Please try again.";

    throw new Error(detail);
  }

  return data as T;
}

// 1. List applicants for one recruiter's posting.
export function getApplicants(
  jobId: number,
  token: string
): Promise<Applicant[]> {
  return send<Applicant[]>(
    `/jobs/${jobId}/applications`,
    token
  );
}

// 2. Save a status change immediately.
export function updateApplicationStatus(
  applicationId: number,
  status: ApplicationStatus,
  token: string
): Promise<Applicant> {
  return send<Applicant>(
    `/applications/${applicationId}/status`,
    token,
    "PATCH",
    { status }
  );
}

// 3. Get one application's status history.
export function getApplicationHistory(
  applicationId: number,
  token: string
): Promise<ApplicationHistoryEntry[]> {
  return send<ApplicationHistoryEntry[]>(
    `/applications/${applicationId}/history`,
    token
  );
}