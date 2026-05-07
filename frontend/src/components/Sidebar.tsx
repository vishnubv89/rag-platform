import { useChatStore } from "../store/chatStore";

type App = "chat" | "knowledge" | "creator" | "search" | "analytics";

interface Props {
  activeApp: App;
  onAppChange: (app: App) => void;
}

const NAV_APPS: { id: App; icon: string; label: string; soon?: boolean }[] = [
  { id: "chat",      icon: "💬", label: "Chat"           },
  { id: "knowledge", icon: "📚", label: "Knowledge Hub" },
  { id: "creator",   icon: "✏️",  label: "Doc Creator",  soon: true },
  { id: "search",    icon: "🖼️", label: "Visual Search", soon: true },
  { id: "analytics", icon: "📊", label: "Analytics",     soon: true },
];

export function Sidebar({ activeApp, onAppChange }: Props) {
  const { sessions, activeSessionId, loadSession, newSession } = useChatStore();

  return (
    <aside
      className="flex flex-col h-full"
      style={{ width: 240, minWidth: 240, background: "#0f1117", borderRight: "1px solid rgba(255,255,255,.06)" }}
    >
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-4 py-4" style={{ borderBottom: "1px solid rgba(255,255,255,.06)" }}>
        <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-sm flex-shrink-0">🧠</div>
        <div>
          <div className="text-white font-semibold text-sm leading-tight">Knowledge Mesh</div>
          <div className="text-xs" style={{ color: "#6b7280" }}>Powered by Agentic RAG</div>
        </div>
      </div>

      {/* App nav */}
      <div className="px-2 pt-3 pb-1">
        <p className="px-2 mb-1 text-xs font-semibold uppercase tracking-widest" style={{ color: "#4b5563" }}>Apps</p>
        {NAV_APPS.map((app) => (
          <button
            key={app.id}
            onClick={() => !app.soon && onAppChange(app.id)}
            className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg mb-0.5 text-sm transition-all"
            style={{
              background: activeApp === app.id ? "rgba(99,102,241,.18)" : "transparent",
              color: app.soon ? "#4b5563" : activeApp === app.id ? "#a5b4fc" : "#9ca3af",
              cursor: app.soon ? "default" : "pointer",
            }}
          >
            <span className="text-base leading-none">{app.icon}</span>
            <span className="flex-1 text-left font-medium">{app.label}</span>
            {app.soon && (
              <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(255,255,255,.06)", color: "#6b7280", fontSize: ".6rem", letterSpacing: ".04em" }}>
                SOON
              </span>
            )}
            {activeApp === app.id && !app.soon && (
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 flex-shrink-0" />
            )}
          </button>
        ))}
      </div>

      {/* Divider */}
      <div style={{ height: 1, background: "rgba(255,255,255,.06)", margin: "8px 16px" }} />

      {/* Chat history (only shown in chat app) */}
      <div className="flex-1 overflow-y-auto px-2">
        <div className="flex items-center justify-between px-2 mb-1">
          <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#4b5563" }}>History</p>
          <button
            onClick={newSession}
            className="text-xs px-2 py-0.5 rounded transition-colors"
            style={{ color: "#6b7280", background: "rgba(255,255,255,.05)" }}
            title="New chat"
          >
            + New
          </button>
        </div>
        {sessions.length === 0 ? (
          <p className="text-xs text-center py-4" style={{ color: "#374151" }}>No history yet</p>
        ) : (
          sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => loadSession(s.id)}
              className="w-full text-left px-2.5 py-2 rounded-lg mb-0.5 text-xs truncate transition-all"
              style={{
                background: s.id === activeSessionId ? "rgba(99,102,241,.12)" : "transparent",
                color: s.id === activeSessionId ? "#a5b4fc" : "#6b7280",
              }}
            >
              {s.preview || "New conversation"}
            </button>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="px-3 py-3" style={{ borderTop: "1px solid rgba(255,255,255,.06)" }}>
        <a
          href="http://localhost:8080"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-xs rounded-lg px-2 py-1.5 transition-colors"
          style={{ color: "#6b7280" }}
        >
          <span>⚙️</span>
          <span>Admin Panel</span>
          <span className="ml-auto opacity-40">↗</span>
        </a>
      </div>
    </aside>
  );
}
