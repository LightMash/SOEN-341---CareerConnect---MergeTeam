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

  // The raw JWT string itself, kept in React state (not just in storage) so
  // that any component below App — like Dashboard — can be handed the token
  // as a normal prop instead of having to read localStorage/sessionStorage
  // directly. Lazily initialized from whichever storage has it, exactly the
  // same way `loading` below already does.
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem("token") || sessionStorage.getItem("token")
  );

  const [loading, setLoading] = useState<boolean>(() =>
    Boolean(localStorage.getItem("token") || sessionStorage.getItem("token"))
  );

  useEffect(() => {
    const storedToken = localStorage.getItem("token") || sessionStorage.getItem("token");

    if (!storedToken) {
      return;
    }

    getProfile(storedToken)
      .then((userData) => setUser(userData))
      .catch(() => {
        localStorage.removeItem("token");
        sessionStorage.removeItem("token");
        setToken(null); // keep the `token` state in sync with storage on failure too
      })
      .finally(() => setLoading(false));
  }, []);

  // Login.tsx/Register.tsx already write the fresh token into
  // localStorage/sessionStorage themselves (before they call onSuccess), so
  // by the time this runs the token is sitting in storage — we just need to
  // pull it into React state here so Dashboard can receive it as a prop.
  // Passed as the `onSuccess` prop to both <Login> and <Register> below,
  // in place of passing `setUser` directly.
  const handleAuthSuccess = (userData: User) => {
    setUser(userData);
    setToken(localStorage.getItem("token") || sessionStorage.getItem("token"));
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    sessionStorage.removeItem("token");
    setUser(null);
    setToken(null); // clear the in-memory copy too, not just storage
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
          element={user ? <Navigate to="/dashboard" replace /> : <Login onSuccess={handleAuthSuccess} />}
        />
        <Route
          path="/register"
          element={user ? <Navigate to="/dashboard" replace /> : <Register onSuccess={handleAuthSuccess} />}
        />

        <Route
          path="/dashboard"
          element={
            user ? (
              // Non-null assertion on `token`: `user` is only ever set (above,
              // and in handleAuthSuccess) right after a token was already
              // written to storage and pulled into this same state, so by the
              // time `user` is truthy, `token` is guaranteed to be too.
              <Dashboard user={user} token={token!} onLogout={handleLogout} />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
