import { useState, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuthStore } from "./store/authStore";
import { handleZitadelCallback, logoutZitadel } from "./auth/zitadelClient";
import { LoginPage } from "./pages/LoginPage";
import { Sidebar } from "./components/Sidebar";
import { ChatWindow } from "./components/ChatWindow";
import { KnowledgeHub } from "./components/KnowledgeHub";
import { DocCreator } from "./components/DocCreator";
import { Analytics } from "./components/Analytics";
import { OrgSelector } from "./components/OrgSelector";
import { FirstRunWizard, useWizardCheck } from "./components/FirstRunWizard";
import { useChatStore } from "./store/chatStore";
import { useIsMobile } from "./hooks/useIsMobile";

const queryClient = new QueryClient();

type App = "chat" | "knowledge" | "creator" | "analytics";

const APP_LABELS: Record<App, string> = {
  chat:      "Chat",
  knowledge: "Knowledge Hub",
  creator:   "Doc Creator",
  analytics: "Analytics",
};

const BOTTOM_NAV: { id: App; label: string; icon: React.ReactNode }[] = [
  {
    id: "chat", label: "Chat",
    icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>,
  },
  {
    id: "knowledge", label: "Knowledge",
    icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></svg>,
  },
  {
    id: "creator", label: "Creator",
    icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" /></svg>,
  },
  {
    id: "analytics", label: "Analytics",
    icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></svg>,
  },
];

function Portal() {
  const [activeApp, setActiveApp] = useState<App>("chat");
  const { newSession, activeOrg } = useChatStore();
  const isMobile = useIsMobile();
  const { user, clearAuth } = useAuthStore();
  const { show: showWizard, setShow: setShowWizard, check: checkWizard } = useWizardCheck(
    activeOrg?.id ?? null,
    user?.role ?? ""
  );

  useEffect(() => { checkWizard(); }, [user?.role]);

  async function logout() {
    // Local session cleanup
    await fetch("/auth/logout", { method: "POST", credentials: "include" }).catch(() => {});
    clearAuth();
    // If the token was issued by Zitadel (RS256), end the Zitadel session too.
    // Import is at module top; this is a no-op if VITE_ZITADEL_CLIENT_ID is unset.
    try { await logoutZitadel(); } catch { /* not a Zitadel session */ }
  }

  return (
    <>
    {showWizard && (
      <FirstRunWizard
        orgId={activeOrg?.id ?? null}
        onDone={() => setShowWizard(false)}
      />
    )}
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar — desktop only */}
      {!isMobile && <Sidebar activeApp={activeApp} onAppChange={(a) => setActiveApp(a as App)} />}

      <div className="flex flex-col flex-1 min-w-0" style={{ background: "#f7f7f8" }}>
        {/* Top bar */}
        <header
          className="flex items-center justify-between px-4 flex-shrink-0"
          style={{ height: 48, background: "#ffffff", borderBottom: "1px solid #e8e8ea" }}
        >
          <div className="flex items-center gap-2">
            {isMobile && (
              <div className="w-6 h-6 rounded-lg flex items-center justify-center mr-1" style={{ background: "#2563eb" }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                </svg>
              </div>
            )}
            <span className="font-semibold text-gray-800 text-sm tracking-tight">
              {APP_LABELS[activeApp]}
            </span>
            <span
              className="text-xs px-1.5 py-0.5 rounded"
              style={{ background: "#f3f4f6", color: "#9ca3af", fontSize: ".6rem", letterSpacing: ".06em" }}
            >
              BETA
            </span>
          </div>

          <div className="flex items-center gap-3">
            {activeApp === "chat" && (
              <button
                onClick={newSession}
                className="text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                style={{ background: "#f3f4f6", color: "#374151" }}
                onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "#e5e7eb")}
                onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "#f3f4f6")}
              >
                New chat
              </button>
            )}
            <OrgSelector />
            <button
              onClick={logout}
              title={`Sign out (${user?.email})`}
              className="flex items-center justify-center w-7 h-7 rounded-lg transition-colors"
              style={{ background: "#f3f4f6", color: "#6b7280" }}
              onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "#fee2e2")}
              onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "#f3f4f6")}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
            </button>
          </div>
        </header>

        {/* App content */}
        <main className="flex-1 overflow-hidden" style={{ paddingBottom: isMobile ? 56 : 0 }}>
          {activeApp === "chat"      && <ChatWindow />}
          {activeApp === "knowledge" && <KnowledgeHub />}
          {activeApp === "creator"   && <DocCreator />}
          {activeApp === "analytics" && <Analytics />}
        </main>
      </div>

      {/* Bottom tab bar — mobile only */}
      {isMobile && (
        <nav
          className="fixed bottom-0 left-0 right-0 flex items-center"
          style={{
            height: 56,
            background: "#ffffff",
            borderTop: "1px solid #e8e8ea",
            zIndex: 50,
          }}
        >
          {BOTTOM_NAV.map((item) => {
            const active = activeApp === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveApp(item.id)}
                className="flex-1 flex flex-col items-center justify-center gap-0.5 py-1 transition-colors"
                style={{ color: active ? "#2563eb" : "#9ca3af" }}
              >
                {item.icon}
                <span style={{ fontSize: ".6rem", fontWeight: active ? 600 : 400 }}>{item.label}</span>
              </button>
            );
          })}
        </nav>
      )}
    </div>
    </>
  );
}

/**
 * Handles the Zitadel OIDC redirect callback (path = /callback).
 * Exchanges the authorisation code for tokens, fetches /auth/me, stores the
 * user, then navigates back to the app root.
 */
function ZitadelCallback() {
  const { setAuth } = useAuthStore();

  useEffect(() => {
    handleZitadelCallback()
      .then(async (oidcUser) => {
        // Zitadel User Agent apps issue opaque access_tokens by default.
        // The id_token is always a signed RS256 JWT and carries the same
        // user claims — use it for backend authentication until the Zitadel
        // app is configured to issue JWT access tokens.
        const bearerToken = oidcUser.id_token ?? oidcUser.access_token;
        const me = await fetch("/auth/me", {
          headers: { Authorization: `Bearer ${bearerToken}` },
        }).then((r) => r.json());
        setAuth(me, bearerToken);
        window.history.replaceState({}, "", "/");
      })
      .catch(() => {
        // If exchange fails (stale state, back-button, etc.), go back to login.
        window.location.replace("/");
      });
  }, []);

  return (
    <div className="flex items-center justify-center min-h-screen" style={{ background: "#f7f7f8" }}>
      <div className="w-6 h-6 rounded-full border-2 border-blue-600 border-t-transparent animate-spin" />
    </div>
  );
}

function AuthBootstrap({ children }: { children: React.ReactNode }) {
  const { setAuth, clearAuth, isLoading } = useAuthStore();

  useEffect(() => {
    // Try to get a new access token using the httpOnly refresh cookie
    fetch("/auth/refresh", { method: "POST", credentials: "include" })
      .then(async (r) => {
        if (!r.ok) { clearAuth(); return; }
        const { access_token } = await r.json();
        const me = await fetch("/auth/me", {
          headers: { Authorization: `Bearer ${access_token}` },
        }).then((r) => r.json());
        setAuth(me, access_token);
      })
      .catch(() => clearAuth());
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen" style={{ background: "#f7f7f8" }}>
        <div className="w-6 h-6 rounded-full border-2 border-blue-600 border-t-transparent animate-spin" />
      </div>
    );
  }

  return <>{children}</>;
}

export default function App() {
  const { user } = useAuthStore();

  // Handle Zitadel OIDC callback before the normal auth bootstrap.
  if (window.location.pathname === "/callback") {
    return <ZitadelCallback />;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <AuthBootstrap>
        {user ? <Portal /> : <LoginPage />}
      </AuthBootstrap>
    </QueryClientProvider>
  );
}
