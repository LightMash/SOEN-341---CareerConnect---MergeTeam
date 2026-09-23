import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Login from "./components/Login";
import Register from "./components/Register";
import Dashboard from "./components/Dashboard";
import { getProfile, type User } from "./api";

function App() {
  // Typing useState<User | null> means `user` is either a full User object
  // or null — nowhere in this file can you accidentally do `user.email`
  // without TypeScript first forcing you to check `user` isn't null.
  const [user, setUser] = useState<User | null>(null);

  const [loading, setLoading] = useState<boolean>(() =>
    Boolean(localStorage.getItem("token") || sessionStorage.getItem("token"))
  );

  useEffect(() => {
    const token = localStorage.getItem("token") || sessionStorage.getItem("token");

    if (!token) {
      return;
    }

    getProfile(token)
      .then((userData) => setUser(userData))
      .catch(() => {
        localStorage.removeItem("token");
        sessionStorage.removeItem("token");
      })
      .finally(() => setLoading(false));
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    sessionStorage.removeItem("token");
    setUser(null);
  };

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
        Loading...
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to={user ? "/dashboard" : "/login"} replace />} />

        <Route
          path="/login"
          element={user ? <Navigate to="/dashboard" replace /> : <Login onSuccess={setUser} />}
        />
        <Route
          path="/register"
          element={user ? <Navigate to="/dashboard" replace /> : <Register onSuccess={setUser} />}
        />

        <Route
          path="/dashboard"
          element={user ? <Dashboard user={user} onLogout={handleLogout} /> : <Navigate to="/login" replace />}
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
