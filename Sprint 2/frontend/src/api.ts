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

// FastAPI reports errors in two shapes: HTTPException sends {"detail": "text"},
// but Pydantic validation failures (HTTP 422) send {"detail": [{loc, msg}, ...]}.
// Without this, a 422 would reach the UI as "[object Object]". This flattens
// either shape (or the legacy {"error": "..."} shape) into one readable string.
function errorMessage(data: { error?: string; detail?: unknown }): string {
  if (data.error) return data.error;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((d: { loc?: (string | number)[]; msg?: string }) => {
        // loc looks like ["body", "education", 0, "school"]; drop the leading "body".
        const where = (d.loc ?? []).slice(1).join(" › ");
        // Pydantic prefixes custom validator errors with "Value error, " — noise for users.
        const msg = (d.msg ?? "Invalid value").replace(/^Value error, /, "");
        return where ? `${where}: ${msg}` : msg;
      })
      .join(". ");
  }
  return "Something went wrong";
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
    throw new Error(errorMessage(data));
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
  is_primary: boolean; // true for the resume applications will use by default
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
// `method` defaults to POST (new upload); replaceResume passes "PUT".
async function requestForm<T>(
  path: string,
  formData: FormData,
  token: string,
  method: "POST" | "PUT" = "POST"
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(errorMessage(data));
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

// Swaps the file behind an existing resume (PUT /api/resume/{id}). Same
// multipart format as uploadResume, so the key must again be "file".
export function replaceResume(id: number, file: File, token: string): Promise<ResumeUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return requestForm<ResumeUploadResponse>(`/resume/${id}`, formData, token, "PUT");
}

// Makes one resume the primary one (the backend clears the flag on the others).
export function setPrimaryResume(id: number, token: string): Promise<Resume> {
  return request<Resume>(`/resume/${id}/primary`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

// --- Profile feature (Sprint 2) --------------------------------------

// These mirror schemas/profile.py — update both together.
export interface EducationItem {
  school: string;
  degree: string;
  start_year: number | null;
  end_year: number | null; // null = still studying
}

export interface ExperienceItem {
  company: string;
  title: string;
  description: string;
  start_year: number | null;
  end_year: number | null; // null = current job
}

// Body of PUT /api/profile/me — matches ProfileUpdate (every editable field).
export interface ProfileUpdate {
  headline: string;
  location: string;
  phone: string;
  summary: string;
  skills: string[];
  education: EducationItem[];
  experience: ExperienceItem[];
  linkedin_url: string;
  github_url: string;
  portfolio_url: string;
}

// Matches ProfileOut: the editable fields plus server-owned ones.
export interface Profile extends ProfileUpdate {
  id: number;
  user_id: number;
  completeness: number; // 0-100, computed by the backend
  missing: string[]; // sections still empty, e.g. ["Skills", "Resume"] — empty when complete
  updated_at: string;
}

// Note: this is /profile/me (the profile feature), not /profile (above),
// which returns the logged-in User and is used for session restore.
export function getMyProfile(token: string): Promise<Profile> {
  return request<Profile>("/profile/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function updateMyProfile(payload: ProfileUpdate, token: string): Promise<Profile> {
  // request() REPLACES its default headers when `headers` is passed, so
  // Content-Type has to be listed again here for the JSON body to be parsed.
  return request<Profile>("/profile/me", {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
}

// --- Profile photo ---------------------------------------------------

// An <img src="..."> can't send an Authorization header, so the photo is
// fetched with fetch() and turned into a temporary "blob:" URL the <img> can
// use. Returns null when the user has no photo (the backend answers 204).
// IMPORTANT: whoever calls this owns the returned URL and should pass it to
// URL.revokeObjectURL() when replacing it, or the browser keeps the bytes in memory.
export async function getProfilePhoto(token: string): Promise<string | null> {
  const res = await fetch(`${API_BASE}/profile/photo`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (res.status === 204) return null;
  if (!res.ok) throw new Error("Couldn't load your profile photo.");

  return URL.createObjectURL(await res.blob());
}

// Same multipart pattern as uploadResume/replaceResume: the form key "file"
// must match the backend's UploadFile parameter name.
export function uploadProfilePhoto(file: File, token: string): Promise<{ message: string }> {
  const formData = new FormData();
  formData.append("file", file);
  return requestForm<{ message: string }>("/profile/photo", formData, token, "PUT");
}

export function deleteProfilePhoto(token: string): Promise<{ message: string }> {
  return request<{ message: string }>("/profile/photo", {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}
