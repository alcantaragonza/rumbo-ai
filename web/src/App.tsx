import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  Link,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";

import { api, type User } from "./api";
import Agents from "./pages/Agents";
import CatalogAdmin from "./pages/CatalogAdmin";
import Chat from "./pages/Chat";
import History from "./pages/History";
import Login from "./pages/Login";
import Reports from "./pages/Reports";

function RequireAuth({ user }: { user: User }) {
  const location = useLocation();

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}

function RequireAdmin({ user, children }: { user: User; children: ReactNode }) {
  if (user.role !== "admin") {
    return <Navigate to="/chat" replace />;
  }
  return <>{children}</>;
}

function Home({ user }: { user: User }) {
  return <Navigate to={user.role === "admin" ? "/admin/catalog" : "/chat"} replace />;
}

function Layout({
  user,
  onLogout,
  children,
}: {
  user: User;
  onLogout: () => void;
  children: ReactNode;
}) {
  return (
    <main className="app">
      <header className="topbar">
        <div>
          <h1>Rumbo AI</h1>
          <p className="hint">
            {user.full_name} · {user.role}
          </p>
        </div>
        <nav className="nav">
          {user.role === "admin" && <Link to="/admin/catalog">Catálogo</Link>}
          <Link to="/chat">Chat</Link>
          <Link to="/agents">Agentes</Link>
          <Link to="/history">Historial</Link>
          <Link to="/reports">Reportes</Link>
          <button onClick={onLogout}>Salir</button>
        </nav>
      </header>
      {children}
    </main>
  );
}

function LoginPage({ onLogin }: { onLogin: (user: User) => void }) {
  return (
    <main className="app">
      <h1>Rumbo AI</h1>
      <p>Plataforma de asistencia y planificación turística con IA.</p>
      <Login onLogin={onLogin} />
    </main>
  );
}

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  async function logout() {
    await api.logout();
    setUser(null);
  }

  if (loading) {
    return (
      <main className="app">
        <p>Cargando…</p>
      </main>
    );
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage onLogin={setUser} />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route element={<RequireAuth user={user} />}>
        <Route path="/" element={<Home user={user} />} />
        <Route
          path="/chat"
          element={
            <Layout user={user} onLogout={() => void logout()}>
              <Chat />
            </Layout>
          }
        />
        <Route
          path="/agents"
          element={
            <Layout user={user} onLogout={() => void logout()}>
              <Agents />
            </Layout>
          }
        />
        <Route
          path="/reports"
          element={
            <Layout user={user} onLogout={() => void logout()}>
              <Reports isAdmin={user.role === "admin"} />
            </Layout>
          }
        />
        <Route
          path="/history"
          element={
            <Layout user={user} onLogout={() => void logout()}>
              <History isAdmin={user.role === "admin"} />
            </Layout>
          }
        />
        <Route
          path="/admin/catalog"
          element={
            <RequireAdmin user={user}>
              <Layout user={user} onLogout={() => void logout()}>
                <CatalogAdmin />
              </Layout>
            </RequireAdmin>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
