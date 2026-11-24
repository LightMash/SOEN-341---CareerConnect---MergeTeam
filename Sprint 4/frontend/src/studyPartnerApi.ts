const API_BASE = "http://localhost:5000/api";

// AI Job Study Partner: these types mirror backend/schemas/study_partner.py.
// If you change a field there, change it here too.

export interface StudyMessage {
  id: number;
  role: "user" | "assistant";
  text: string;
  suggested_questions: string[]; // empty on the user's messages
  created_at: string; // UTC, no timezone suffix
}

export interface StudyChat {
  job_id: number;
  messages: StudyMessage[]; // oldest first
  starter_questions: string[]; // only while the chat is empty
}

export interface Certification {
  id: string;
  name: string;
  issuer: string;
  level: string; // "Entry" | "Intermediate"
  topic: string; // the skill it matches
  summary: string;
  url: string; // the official page
}

// Longest message the backend accepts (MAX_MESSAGE_LENGTH).
export const MAX_MESSAGE_LENGTH = 1000;

// Same idea as resumeFeedbackApi.ts's send(): the backend's `detail` text is
// already written for users (e.g. "The AI service is busy right now..."), so it
// is passed through as the error message.
export class StudyError extends Error {
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

  // DELETE answers 204 with no body, hence the catch.
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail =
      typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.";
    throw new StudyError(response.status, detail);
  }
  return data as T;
}

// GET /api/jobs/{id}/study-chat: the saved conversation (fast, never calls the AI).
export function getStudyChat(jobId: number, token: string): Promise<StudyChat> {
  return send<StudyChat>(`/jobs/${jobId}/study-chat`, token);
}

// POST /api/jobs/{id}/study-chat/messages: asks Gemini (a few seconds) and
// returns the WHOLE updated chat. Nothing is saved if the AI fails.
export function sendStudyMessage(jobId: number, text: string, token: string): Promise<StudyChat> {
  return send<StudyChat>(`/jobs/${jobId}/study-chat/messages`, token, "POST", { text });
}

// DELETE /api/jobs/{id}/study-chat: start over.
export async function resetStudyChat(jobId: number, token: string): Promise<void> {
  await send<unknown>(`/jobs/${jobId}/study-chat`, token, "DELETE");
}

// GET /api/jobs/{id}/certifications: curated certifications that fit the
// posting (no AI; may be an empty list).
export async function getCertifications(jobId: number, token: string): Promise<Certification[]> {
  const data = await send<{ job_id: number; certifications: Certification[] }>(
    `/jobs/${jobId}/certifications`,
    token
  );
  return data.certifications;
}
