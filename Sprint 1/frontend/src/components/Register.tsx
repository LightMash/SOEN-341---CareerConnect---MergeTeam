import { useState, type ChangeEvent, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { registerUser, type User, type RegisterPayload, type Role } from "../api";
import "../styles/auth.css";

interface RegisterProps {
  onSuccess?: (user: User) => void;
}

export default function Register({ onSuccess }: RegisterProps) {
  const [form, setForm] = useState<RegisterPayload>({
    full_name: "",
    email: "",
    password: "",
    role: "job_seeker",
  });
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [emailError, setEmailError] = useState<string>("");

  const navigate = useNavigate();

  // Loose format check (has an "@", something before and after it, and a
  // "." in the domain part) — just fast UX feedback. The backend's
  // Pydantic EmailStr validation is the real source of truth.
  const isValidEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

  // Covers both <input> and <select> changes, since this form has both.
  const handleChange = (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
    if (e.target.name === "email") setEmailError(""); // clear stale error while typing
  };

  const handleEmailBlur = () => {
    if (form.email && !isValidEmail(form.email)) {
      setEmailError("Please enter a valid email address");
    } else {
      setEmailError("");
    }
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!isValidEmail(form.email)) {
      setEmailError("Please enter a valid email address");
      return;
    }

    setError("");
    setLoading(true);
    try {
      const data = await registerUser(form);
      localStorage.setItem("token", data.token);
      onSuccess?.(data.user);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-icon">
          <div className="auth-icon-dot" />
        </div>

        <h1 className="auth-title">Create your account</h1>
        <p className="auth-subtitle">Join CareerConnect to get started.</p>

        <div className="auth-tabs">
          <Link to="/register" className="auth-tab active">Sign up</Link>
          <Link to="/login" className="auth-tab">Log in</Link>
        </div>

        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="auth-field">
            <label className="auth-label">Full name</label>
            <input
              className="auth-input"
              type="text"
              name="full_name"
              placeholder="Enter your full name"
              value={form.full_name}
              onChange={handleChange}
              required
            />
          </div>

          <div className="auth-field">
            <label className="auth-label">Email</label>
            <input
              className="auth-input"
              type="email"
              name="email"
              placeholder="Enter your email"
              value={form.email}
              onChange={handleChange}
              onBlur={handleEmailBlur}
              required
            />
            {emailError && <div className="auth-field-error">{emailError}</div>}
          </div>

          <div className="auth-field">
            <label className="auth-label">Password</label>
            <div className="auth-password-wrapper">
              <input
                className="auth-input"
                type={showPassword ? "text" : "password"}
                name="password"
                placeholder="At least 8 characters"
                value={form.password}
                onChange={handleChange}
                required
                minLength={8}
                maxLength={72} // matches schemas/auth.py's Field(min_length=8, max_length=72)
              />
              <button
                type="button"
                className="auth-eye-btn"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a18.9 18.9 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.87 18.87 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          <div className="auth-field">
            <label className="auth-label">I am a</label>
            <select
              className="auth-input"
              name="role"
              value={form.role}
              onChange={(e: ChangeEvent<HTMLSelectElement>) =>
                setForm({ ...form, role: e.target.value as Role })
              }
            >
              <option value="job_seeker">Job Seeker</option>
              <option value="recruiter">Recruiter</option>
            </select>
          </div>

          <button type="submit" className="auth-submit-btn" disabled={loading}>
            {loading ? "Creating account..." : "Sign up"}
          </button>
        </form>

        <button type="button" className="auth-google-btn">
          Sign up with Google
        </button>

        <p className="auth-bottom-text">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}
