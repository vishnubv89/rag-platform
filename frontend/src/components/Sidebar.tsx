import { useChatStore } from "../store/chatStore";

type App = "chat" | "knowledge" | "creator" | "dashboards" | "analytics";

interface Props {
  activeApp: App;
  onAppChange: (app: App) => void;
}

const NAV_APPS: { id: App; label: string; icon: React.ReactNode; soon?: boolean }[] = [
  {
    id: "chat", label: "Chat",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
  },
  {
    id: "knowledge", label: "Knowledge Hub",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      </svg>
    ),
  },
  {
    id: "creator", label: "Doc Creator",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
      </svg>
    ),
  },
  {
    id: "dashboards", label: "Dashboards",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  {
    id: "analytics", label: "Analytics",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" />
      </svg>
    ),
  },
];

export function Sidebar({ activeApp, onAppChange }: Props) {
  const { sessions, activeSessionId, loadSession, newSession } = useChatStore();

  return (
    <aside
      className="flex flex-col h-full sidebar-scroll"
      style={{ width: 228, minWidth: 228, background: "#111827", borderRight: "1px solid rgba(255,255,255,.05)" }}
    >
      {/* Brand */}
      <div className="px-5 py-5" style={{ borderBottom: "1px solid rgba(255,255,255,.05)" }}>
        <div className="flex items-center gap-2.5">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ background: "#2563eb" }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
          </div>
          <div>
            <div className="text-white font-semibold text-sm leading-tight tracking-tight">Knowledge Mesh</div>
            <div className="text-xs mt-0.5" style={{ color: "#4b5563" }}>Agentic RAG</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="px-3 pt-4 pb-2">
        <p className="px-2 mb-2 text-xs font-medium uppercase tracking-widest" style={{ color: "#374151", letterSpacing: ".08em", fontSize: ".6rem" }}>
          Apps
        </p>
        {NAV_APPS.map((app) => {
          const active = activeApp === app.id && !app.soon;
          return (
            <button
              key={app.id}
              onClick={() => !app.soon && onAppChange(app.id)}
              className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg mb-0.5 text-sm transition-colors"
              style={{
                background: active ? "rgba(37,99,235,.15)" : "transparent",
                color: app.soon ? "#374151" : active ? "#93c5fd" : "#9ca3af",
                cursor: app.soon ? "default" : "pointer",
              }}
              onMouseEnter={(e) => {
                if (!app.soon && !active)
                  (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,.04)";
              }}
              onMouseLeave={(e) => {
                if (!active)
                  (e.currentTarget as HTMLButtonElement).style.background = "transparent";
              }}
            >
              <span className="flex-shrink-0">{app.icon}</span>
              <span className="flex-1 text-left font-medium text-xs">{app.label}</span>
              {app.soon && (
                <span
                  className="text-xs rounded px-1.5 py-0.5"
                  style={{ background: "rgba(255,255,255,.05)", color: "#4b5563", fontSize: ".6rem", letterSpacing: ".06em" }}
                >
                  SOON
                </span>
              )}
              {active && (
                <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ background: "#2563eb" }} />
              )}
            </button>
          );
        })}
      </nav>

      <div style={{ height: 1, background: "rgba(255,255,255,.05)", margin: "4px 16px 8px" }} />

      {/* Chat history */}
      <div className="flex-1 overflow-y-auto px-3 sidebar-scroll">
        <div className="flex items-center justify-between px-2 mb-2">
          <p className="text-xs font-medium uppercase tracking-widest" style={{ color: "#374151", letterSpacing: ".08em", fontSize: ".6rem" }}>
            History
          </p>
          <button
            onClick={newSession}
            className="text-xs px-2 py-0.5 rounded transition-colors"
            style={{ color: "#4b5563" }}
            onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.color = "#9ca3af")}
            onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.color = "#4b5563")}
            title="New chat"
          >
            + New
          </button>
        </div>
        {sessions.length === 0 ? (
          <p className="text-xs px-2 py-2" style={{ color: "#374151" }}>No history yet</p>
        ) : (
          sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => loadSession(s.id)}
              className="w-full text-left px-2.5 py-1.5 rounded-lg mb-0.5 text-xs truncate transition-colors"
              style={{
                background: s.id === activeSessionId ? "rgba(255,255,255,.06)" : "transparent",
                color: s.id === activeSessionId ? "#d1d5db" : "#4b5563",
              }}
            >
              {s.preview || "New conversation"}
            </button>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="px-3 py-3" style={{ borderTop: "1px solid rgba(255,255,255,.05)" }}>
        <a
          href="http://localhost:8080"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-xs rounded-lg px-2.5 py-2 transition-colors"
          style={{ color: "#4b5563" }}
          onMouseEnter={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = "#6b7280")}
          onMouseLeave={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = "#4b5563")}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3" /><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14" />
          </svg>
          <span>Admin Panel</span>
          <svg className="ml-auto" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: .35 }}>
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /><polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" />
          </svg>
        </a>
      </div>
    </aside>
  );
}
