import type { User } from "../api";

interface DashboardProps {
  user: User;
  onLogout: () => void;
}

export default function Dashboard({ user, onLogout }: DashboardProps) {
  return (
    <div style={{ maxWidth: 480, margin: "60px auto", textAlign: "center" }}>
      <h1>Welcome, {user.full_name}!</h1>
      <p>Email: {user.email}</p>
      <p>Role: {user.role}</p>

      <p style={{ color: "#64748b" }}>This is a placeholder dashboard.</p>

      <button
        onClick={onLogout}
        style={{
          padding: "10px 20px",
          background: "#2563eb",
          color: "#fff",
          border: "none",
          borderRadius: 8,
          cursor: "pointer",
        }}
      >
        Log out
      </button>
    </div>
  );
}
