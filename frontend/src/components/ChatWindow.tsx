import { useEffect, useRef, useState } from "react";
import { MessageBubble } from "./MessageBubble";
import { MessageInput } from "./MessageInput";
import { FileUpload } from "./FileUpload";
import { useChat } from "../hooks/useChat";
import { useChatStore } from "../store/chatStore";

const SUGGESTIONS = [
  "Summarize the key documents in my knowledge base",
  "What topics are covered across all sources?",
  "Find information about incident response procedures",
  "What are the latest updates from the knowledge base?",
];

export function ChatWindow() {
  const { messages } = useChatStore();
  const { send, loading, error } = useChat();
  const [showUpload, setShowUpload] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full max-w-xl mx-auto text-center">
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl mb-5"
              style={{ background: "rgba(99,102,241,.08)", border: "1px solid rgba(99,102,241,.15)" }}
            >
              🧠
            </div>
            <h2 className="text-lg font-semibold text-gray-800 mb-2">Ask your Knowledge Mesh</h2>
            <p className="text-gray-400 text-sm mb-8 leading-relaxed">
              Answers grounded in your connected sources — ServiceNow, SharePoint, Confluence, and uploaded documents.
            </p>
            <div className="grid grid-cols-1 gap-2 w-full">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left px-4 py-3 rounded-xl text-sm transition-all"
                  style={{ background: "#f9fafb", border: "1px solid #f0f0f0", color: "#374151" }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.borderColor = "#c7d2fe";
                    (e.currentTarget as HTMLButtonElement).style.background = "#eef2ff";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.borderColor = "#f0f0f0";
                    (e.currentTarget as HTMLButtonElement).style.background = "#f9fafb";
                  }}
                >
                  <span className="text-indigo-400 mr-2">✦</span>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((m) => <MessageBubble key={m.id} message={m} />)}
            {loading && (
              <div className="flex justify-start mb-4">
                <div
                  className="px-4 py-3 rounded-2xl rounded-bl-sm text-sm"
                  style={{ background: "#f9fafb", border: "1px solid #f0f0f0" }}
                >
                  <span className="typing-dot" style={{ color: "#9ca3af" }} />
                  <span className="typing-dot mx-1" style={{ color: "#9ca3af" }} />
                  <span className="typing-dot" style={{ color: "#9ca3af" }} />
                </div>
              </div>
            )}
            {error && (
              <div className="text-center text-sm py-2 px-4 rounded-lg mx-auto max-w-sm" style={{ background: "#fef2f2", color: "#ef4444" }}>
                {error}
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Upload toggle */}
      <div className="px-6 pb-1 flex items-center justify-between">
        <span className="text-xs" style={{ color: "#9ca3af" }}>
          {messages.length > 0 && `${messages.length} message${messages.length !== 1 ? "s" : ""}`}
        </span>
        <button
          onClick={() => setShowUpload((v) => !v)}
          className="flex items-center gap-1.5 text-xs transition-colors"
          style={{ color: showUpload ? "#6366f1" : "#9ca3af" }}
        >
          <span>📎</span>
          {showUpload ? "Hide upload" : "Upload document"}
        </button>
      </div>
      {showUpload && <FileUpload />}

      <MessageInput onSend={send} loading={loading} />
    </div>
  );
}
