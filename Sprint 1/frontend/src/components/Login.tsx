import { useState, type ChangeEvent, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { loginUser, type User, type LoginPayload } from "../api";
import "../styles/auth.css";

// Props this component accepts. onSuccess is optional (the `?`) — App.jsx
// passes it, but the component shouldn't crash if some other caller doesn't.
interface LoginProps {
  onSuccess?: (user: User) => void;
}

export default function Login({ onSuccess }: LoginProps) {
  // Typing useState with <LoginPayload> means `form.email`/`form.password`
  // are checked against that exact shape — e.g. typo'ing `form.emial` would
  // now be a compile-time error instead of a silent undefined at runtime.
  const [form, setForm] = useState<LoginPayload>({ email: "", password: "" });

  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [remember, setRemember] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  const navigate = useNavigate();

  // React.ChangeEvent<HTMLInputElement> types `e.target.name`/`e.target.value`
  // correctly — this is one of the concrete payoffs of TypeScript here: without
  // it, `e.target` is typed as EventTarget, which doesn't even have `.value`.
  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await loginUser(form);

      const storage = remember ? localStorage : sessionStorage;
      storage.setItem("token", data.token);

      onSuccess?.(data.user); // optional chaining — same as `onSuccess && onSuccess(...)`
      navigate("/dashboard");
    } catch (err) {
      // `err` from a catch block is typed `unknown` in strict TS — we can't
      // assume it has `.message` without checking first.
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

        <h1 className="auth-title">Log in to your account</h1>
        <p className="auth-subtitle">Welcome back! Please enter your details.</p>

        <div className="auth-tabs">
          <Link to="/register" className="auth-tab">Sign up</Link>
          <Link to="/login" className="auth-tab active">Log in</Link>
        </div>

        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={handleSubmit}>
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
                placeholder="Enter your password"
                value={form.password}
                onChange={handleChange}
                required
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

          <div className="auth-row">
            <label className="auth-remember">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e: ChangeEvent<HTMLInputElement>) => setRemember(e.target.checked)}
              />
              Remember for 30 days
            </label>

            <button type="button" className="auth-forgot-link">
              Forgot password
            </button>
          </div>

          <button type="submit" className="auth-submit-btn" disabled={loading}>
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <button type="button" className="auth-google-btn">
          <span>🇬</span> Sign in with Google
        </button>

        <p className="auth-bottom-text">
          Don't have an account? <Link to="/register">Sign up</Link>
        </p>
      </div>
    </div>
  );
}
