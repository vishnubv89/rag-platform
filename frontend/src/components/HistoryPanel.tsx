import { useEffect, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { listSessions, getSession } from "../api/client";
import { useChatStore } from "../store/chatStore";
import type { ChatMessage } from "../types";

interface SessionMeta {
  session_id: string;
  preview: string;
  message_count: number;
  last_active: string;
}

export function HistoryPanel() {
  const { activeSessionId, sessionId, newSession, loadSession } = useChatStore();
  const [dbSessions, setDbSessions] = useState<SessionMeta[]>([]);

  useEffect(() => {
    listSessions()
      .then((r) => setDbSessions(r.sessions))
      .catch(() => {/* not logged in or offline — stay silent */});
  }, [sessionId]); // re-fetch whenever a new session completes

  async function handleLoad(meta: SessionMeta) {
    if (meta.session_id === activeSessionId) return;
    try {
      const data = await getSession(meta.session_id);
      const messages: ChatMessage[] = data.messages.map((m) => ({
        id: uuidv4(),
        role: m.role as "user" | "assistant",
        content: m.content,
        sourceChunkIds: m.source_chunk_ids,
        sources: [],
        loopCount: 0,
        timestamp: new Date(m.timestamp),
        logId: m.log_id ?? undefined,
        feedback: (m.feedback as 1 | -1 | null) ?? undefined,
      }));
      loadSession(meta.session_id, messages);
    } catch {
      // fall through — session stays empty
    }
  }

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
        {dbSessions.length === 0 && (
          <p className="text-xs text-gray-400 text-center mt-6">No history yet</p>
        )}
        {dbSessions.map((s) => (
          <button
            key={s.session_id}
            onClick={() => handleLoad(s)}
            className={`w-full text-left px-3 py-2 text-xs truncate border-b border-gray-100 hover:bg-white transition-colors ${
              s.session_id === activeSessionId ? "bg-white font-medium text-indigo-700" : "text-gray-600"
            }`}
          >
            {s.preview || "New conversation"}
          </button>
        ))}
      </div>
    </aside>
  );
}
