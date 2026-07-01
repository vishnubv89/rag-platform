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
  const { send, loading, error, suggestions, streamingContent } = useChat();
  const [showUpload, setShowUpload] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, suggestions]);

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--cds-surface)" }}>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full max-w-lg mx-auto text-center">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center mb-5"
              style={{ background: "var(--cds-accent-tint)", border: "1px solid #F5C4B3" }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--cds-accent)" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
            </div>
            <h2 className="text-base font-semibold mb-2" style={{ color: "var(--cds-text-primary)" }}>Ask your knowledge base</h2>
            <p className="text-sm mb-7 leading-relaxed" style={{ color: "var(--cds-text-muted)" }}>
              Answers grounded in your connected sources — ServiceNow, SharePoint, Confluence, and uploaded documents.
            </p>
            <div className="grid grid-cols-1 gap-1.5 w-full">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left px-4 py-2.5 rounded-lg text-sm transition-colors"
                  style={{ background: "var(--cds-surface-tint)", border: "1px solid var(--cds-border)", color: "var(--cds-text-secondary)" }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background = "var(--cds-accent-tint)";
                    (e.currentTarget as HTMLButtonElement).style.borderColor = "#F5C4B3";
                    (e.currentTarget as HTMLButtonElement).style.color = "var(--cds-accent-text)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background = "var(--cds-surface-tint)";
                    (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--cds-border)";
                    (e.currentTarget as HTMLButtonElement).style.color = "var(--cds-text-secondary)";
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
                  className="max-w-[72%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap"
                  style={{ background: "var(--cds-surface)", color: "var(--cds-text-primary)", border: "1px solid var(--cds-border)", borderRadius: "4px 16px 16px 16px" }}
                >
                  {streamingContent ? (
                    <>
                      {streamingContent}
                      <span
                        className="inline-block w-0.5 h-4 ml-0.5 align-middle animate-pulse"
                        style={{ background: "var(--cds-text-secondary)" }}
                      />
                    </>
                  ) : (
                    <>
                      <span className="typing-dot" style={{ color: "var(--cds-text-muted)" }} />
                      <span className="typing-dot mx-1" style={{ color: "var(--cds-text-muted)" }} />
                      <span className="typing-dot" style={{ color: "var(--cds-text-muted)" }} />
                    </>
                  )}
                </div>
              </div>
            )}
            {error && (
              <div className="text-center text-xs py-2 px-4 rounded-lg mx-auto max-w-sm mt-2" style={{ background: "#FCEBEB", color: "#791F1F", border: "1px solid #F7C1C1" }}>
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
                      background: "var(--cds-surface-tint)",
                      border: "1px solid var(--cds-border)",
                      color: "var(--cds-text-secondary)",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "var(--cds-accent-tint)";
                      e.currentTarget.style.borderColor = "#F5C4B3";
                      e.currentTarget.style.color = "var(--cds-accent-text)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "var(--cds-surface-tint)";
                      e.currentTarget.style.borderColor = "var(--cds-border)";
                      e.currentTarget.style.color = "var(--cds-text-secondary)";
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
          style={{ color: showUpload ? "var(--cds-accent)" : "var(--cds-text-muted)" }}
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
