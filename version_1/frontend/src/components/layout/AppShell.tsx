import { Outlet } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";
import { useApiStatus } from "../../hooks/useApiStatus";
import Sidebar from "./Sidebar";

function AppShell() {
  const apiStatus = useApiStatus();
  const auth = useAuth();

  const statusLabel = {
    checking: "Checking API",
    connected: "API Connected",
    unavailable: "API Unavailable",
  }[apiStatus.status];

  return (
    <div className="app-shell">
      <Sidebar />

      <div className="app-main">
        <header className="app-header">
          <div>
            <p className="header-eyebrow">
              PERSONAL INTELLIGENCE
            </p>

            <h1>PAIS</h1>
          </div>

          <div className="header-status-group">
            <div
              className={`connection-status connection-status-${apiStatus.status}`}
              title={
                apiStatus.message ??
                "PAIS API status"
              }
            >
              <span className="connection-dot" />

              <span>{statusLabel}</span>
            </div>

            <div
              className={`auth-status ${
                auth.isAuthenticated
                  ? "auth-status-authenticated"
                  : "auth-status-unauthenticated"
              }`}
            >
              <span className="auth-dot" />

              <span>
                {auth.isAuthenticated
                  ? "Authenticated"
                  : "Not authenticated"}
              </span>
            </div>
          </div>
        </header>

        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default AppShell;