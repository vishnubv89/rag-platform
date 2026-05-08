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
  const { send, loading, error, suggestions } = useChat();
  const [showUpload, setShowUpload] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, suggestions]);

  return (
    <div className="flex flex-col h-full" style={{ background: "#ffffff" }}>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full max-w-lg mx-auto text-center">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center mb-5"
              style={{ background: "#eff6ff", border: "1px solid #bfdbfe" }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
            </div>
            <h2 className="text-base font-semibold text-gray-800 mb-2">Ask your knowledge base</h2>
            <p className="text-sm text-gray-400 mb-7 leading-relaxed">
              Answers grounded in your connected sources — ServiceNow, SharePoint, Confluence, and uploaded documents.
            </p>
            <div className="grid grid-cols-1 gap-1.5 w-full">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left px-4 py-2.5 rounded-lg text-sm text-gray-600 transition-colors"
                  style={{ background: "#f7f7f8", border: "1px solid #e8e8ea" }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background = "#eff6ff";
                    (e.currentTarget as HTMLButtonElement).style.borderColor = "#bfdbfe";
                    (e.currentTarget as HTMLButtonElement).style.color = "#1d4ed8";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background = "#f7f7f8";
                    (e.currentTarget as HTMLButtonElement).style.borderColor = "#e8e8ea";
                    (e.currentTarget as HTMLButtonElement).style.color = "#4b5563";
                  }}
                >
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
                  className="px-4 py-3 rounded-2xl rounded-bl-sm"
                  style={{ background: "#f7f7f8", border: "1px solid #e8e8ea" }}
                >
                  <span className="typing-dot" style={{ color: "#9ca3af" }} />
                  <span className="typing-dot mx-1" style={{ color: "#9ca3af" }} />
                  <span className="typing-dot" style={{ color: "#9ca3af" }} />
                </div>
              </div>
            )}
            {error && (
              <div className="text-center text-xs py-2 px-4 rounded-lg mx-auto max-w-sm mt-2" style={{ background: "#fef2f2", color: "#dc2626", border: "1px solid #fecaca" }}>
                {error}
              </div>
            )}

            {/* Follow-up suggestion chips */}
            {!loading && suggestions.length > 0 && (
              <div className="flex flex-col gap-1.5 mt-3 mb-1 max-w-lg">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="text-left px-3.5 py-2 rounded-xl text-sm transition-colors"
                    style={{
                      background: "#f7f7f8",
                      border: "1px solid #e8e8ea",
                      color: "#4b5563",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "#eff6ff";
                      e.currentTarget.style.borderColor = "#bfdbfe";
                      e.currentTarget.style.color = "#1d4ed8";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "#f7f7f8";
                      e.currentTarget.style.borderColor = "#e8e8ea";
                      e.currentTarget.style.color = "#4b5563";
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Upload strip */}
      <div className="px-6 pb-1 flex items-center justify-end" style={{ borderTop: messages.length > 0 ? "none" : undefined }}>
        <button
          onClick={() => setShowUpload((v) => !v)}
          className="flex items-center gap-1.5 text-xs transition-colors py-1"
          style={{ color: showUpload ? "#2563eb" : "#9ca3af" }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
          </svg>
          {showUpload ? "Hide upload" : "Upload document"}
        </button>
      </div>
      {showUpload && <FileUpload />}

      <MessageInput onSend={send} loading={loading} />
    </div>
  );
}
