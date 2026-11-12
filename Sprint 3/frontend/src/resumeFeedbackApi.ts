const API_BASE = "http://localhost:5000/api";

// AI Resume Feedback : These types mirror
// backend/schemas/resume_feedback.py — if you change a field there, change it
// here too.

export type SuggestionCategory = "impact" | "clarity" | "skills" | "grammar" | "formatting" | "content";
export type SuggestionPriority = "high" | "medium" | "low";

export interface Suggestion {
  id: number; // position in the list, used to remember accept/dismiss
  section: string;
  category: SuggestionCategory;
  priority: SuggestionPriority;
  original: string; // "" means "add something new"
  suggested: string;
  reason: string;
  can_apply: boolean; // `original` really appears in the resume text
}

export interface ResumeFeedback {
  id: number;
  resume_id: number;
  job_id: number | null; // set when the feedback was tailored to a posting
  overall_score: number; // 0-100
  summary: string;
  strengths: string[];
  suggestions: Suggestion[];
  model: string;
  created_at: string; // UTC, no timezone suffix
  is_outdated: boolean; // the resume file was replaced after this review
}

// Same idea as notificationsApi.ts's send(), plus the HTTP status on errors,
// because a 404 on GET simply means "no feedback yet" (not a failure).
class FeedbackError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function send<T>(path: string, token: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail =
      typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.";
    throw new FeedbackError(response.status, detail);
  }
  return data as T;
}

// POST /api/resume/{id}/feedback — asks Gemini for a NEW review (slow: several
// seconds). Pass a jobId to tailor the feedback to that posting.
export function requestFeedback(
  resumeId: number,
  jobId: number | null,
  token: string
): Promise<ResumeFeedback> {
  return send<ResumeFeedback>(`/resume/${resumeId}/feedback`, token, "POST", { job_id: jobId });
}

// GET /api/resume/{id}/feedback — the latest SAVED review (fast, no AI call).
// Resolves to null when this resume has never been reviewed.
export async function getLatestFeedback(resumeId: number, token: string): Promise<ResumeFeedback | null> {
  try {
    return await send<ResumeFeedback>(`/resume/${resumeId}/feedback`, token);
  } catch (err) {
    if (err instanceof FeedbackError && err.status === 404) return null;
    throw err;
  }
}
