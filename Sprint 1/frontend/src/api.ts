const API_BASE = "http://localhost:5000/api";

// These types mirror your backend's Pydantic schemas exactly
// (schemas/auth.py). Keeping them in sync by hand is a real tradeoff of
// having a Python backend + TypeScript frontend as two separate codebases —
// if you add/rename a field in schemas/auth.py, update it here too.

export type Role = "job_seeker" | "recruiter";

// Matches schemas/auth.py's UserOut — notice password_hash is NOT here,
// because the backend never sends it back either.
export interface User {
  id: number;
  full_name: string;
  email: string;
  role: Role;
}

// Matches schemas/auth.py's TokenResponse
export interface TokenResponse {
  message: string;
  token: string;
  user: User;
}

// What the frontend sends to POST /api/register — matches UserCreate
export interface RegisterPayload {
  full_name: string;
  email: string;
  password: string;
  role: Role;
}

// What the frontend sends to POST /api/login — matches UserLogin
export interface LoginPayload {
  email: string;
  password: string;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  // FastAPI error responses are JSON too, so this is safe even on failure —
  // we just don't know yet whether it's a success or error shape, hence `any`
  // here specifically (the one deliberate escape hatch in this file).
  const data = await res.json();

  if (!res.ok) {
    // FastAPI's HTTPException returns {"detail": "..."}; older code paths
    // (or a non-FastAPI error) might use {"error": "..."} instead — check both.
    throw new Error(data.error || data.detail || "Something went wrong");
  }

  return data as T;
}

export function registerUser(payload: RegisterPayload): Promise<TokenResponse> {
  return request<TokenResponse>("/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function loginUser(payload: LoginPayload): Promise<TokenResponse> {
  return request<TokenResponse>("/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getProfile(token: string): Promise<User> {
  return request<User>("/profile", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

// --- Resume upload feature -------------------------------------------

// Matches schemas/resume.py's ResumeOut
export interface Resume {
  id: number;
  user_id: number;
  filename: string;
  uploaded_at: string; // ISO date string over JSON — not a real Date object
}

// Matches schemas/resume.py's ResumeUploadResponse
export interface ResumeUploadResponse {
  message: string;
  resume: Resume;
}

// A second request helper, specifically for file uploads. We deliberately
// do NOT set "Content-Type" here — the browser sets it automatically
// (including the multipart boundary) when the body is a FormData object,
// and setting it manually ourselves would actually break the upload.
async function requestForm<T>(path: string, formData: FormData, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.error || data.detail || "Something went wrong");
  }

  return data as T;
}

export function uploadResume(file: File, token: string): Promise<ResumeUploadResponse> {
  // FormData is the browser's built-in way to build a multipart request —
  // this is what actually carries the real file bytes to the server.
  const formData = new FormData();
  formData.append("file", file); // "file" must match the backend's UploadFile param name

  return requestForm<ResumeUploadResponse>("/resume/upload", formData, token);
}

export function listMyResumes(token: string): Promise<Resume[]> {
  return request<Resume[]>("/resume/mine", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function deleteResume(id: number, token: string): Promise<{ message: string }> {
  return request<{ message: string }>(`/resume/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}

// Downloads aren't JSON, so this bypasses request<T>() entirely. It fetches
// the raw file bytes as a Blob, then uses a throwaway <a> tag to trigger the
// browser's normal "Save As" behavior — done manually (instead of just
// linking to the URL) because this request needs an Authorization header.
export async function downloadResume(id: number, filename: string, token: string): Promise<void> {
  const res = await fetch(`${API_BASE}/resume/${id}/download`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Download failed");
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = filename; // suggests the original filename in the save dialog
  link.click();

  URL.revokeObjectURL(url); // release the memory now that the download's kicked off
}