import { useChatStore } from "../store/chatStore";

export function HistoryPanel() {
  const { sessions, activeSessionId, loadSession, newSession } = useChatStore();

  return (
    <aside className="w-56 flex-shrink-0 border-r border-gray-100 bg-gray-50 flex flex-col h-full">
      <div className="p-3 border-b border-gray-100">
        <button
          onClick={newSession}
          className="w-full text-sm text-left px-3 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
        >
          + New chat
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 && (
          <p className="text-xs text-gray-400 text-center mt-6">No history yet</p>
        )}
        {sessions.map((s) => (
          <button
            key={s.id}
            onClick={() => loadSession(s.id)}
            className={`w-full text-left px-3 py-2 text-xs truncate border-b border-gray-100 hover:bg-white transition-colors ${
              s.id === activeSessionId ? "bg-white font-medium text-indigo-700" : "text-gray-600"
            }`}
          >
            {s.preview || "New conversation"}
          </button>
        ))}
      </div>
    </aside>
  );
}
