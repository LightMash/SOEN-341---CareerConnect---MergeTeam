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

  const navigate = useNavigate();

  // Covers both <input> and <select> changes, since this form has both.
  const handleChange = (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
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
              required
            />
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
                {showPassword ? "No" : "Yes"}
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
          <span>🇬</span> Sign up with Google
        </button>

        <p className="auth-bottom-text">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}
