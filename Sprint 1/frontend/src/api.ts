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
