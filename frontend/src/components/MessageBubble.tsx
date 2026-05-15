import { useState } from "react";
import { SourceCitations } from "./SourceCitations";
import { submitFeedback } from "../api/client";
import type { ChatMessage } from "../types";

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const [feedback, setFeedback] = useState<1 | -1 | null>(message.feedback ?? null);

  async function handleFeedback(value: 1 | -1) {
    if (feedback !== null || !message.logId) return;
    setFeedback(value);
    try {
      await submitFeedback(message.logId, value);
    } catch {
      setFeedback(null); // revert on error
    }
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-5`}>
      <div className={`max-w-[72%] ${isUser ? "order-2" : "order-1"}`}>
        <div
          className="px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap"
          style={
            isUser
              ? { background: "#18181b", color: "#f9fafb", borderRadius: "16px 16px 4px 16px" }
              : { background: "#ffffff", color: "#111827", border: "1px solid #e8e8ea", borderRadius: "4px 16px 16px 16px" }
          }
        >
          {message.content}
        </div>

        {!isUser && (
          <>
            <SourceCitations sources={message.sources} loopCount={message.loopCount} />
            {message.logId && (
              <div className="flex items-center gap-2 mt-1.5">
                <button
                  onClick={() => handleFeedback(1)}
                  disabled={feedback !== null}
                  title="Helpful"
                  className="transition-opacity"
                  style={{ opacity: feedback !== null && feedback !== 1 ? 0.3 : 1 }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill={feedback === 1 ? "#16a34a" : "none"} stroke={feedback === 1 ? "#16a34a" : "#9ca3af"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z" />
                    <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
                  </svg>
                </button>
                <button
                  onClick={() => handleFeedback(-1)}
                  disabled={feedback !== null}
                  title="Not helpful"
                  className="transition-opacity"
                  style={{ opacity: feedback !== null && feedback !== -1 ? 0.3 : 1 }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill={feedback === -1 ? "#dc2626" : "none"} stroke={feedback === -1 ? "#dc2626" : "#9ca3af"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z" />
                    <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
                  </svg>
                </button>
              </div>
            )}
          </>
        )}

        <div className={`text-xs mt-1 ${isUser ? "text-right" : "text-left"}`} style={{ color: "#d1d5db" }}>
          {new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </div>
      </div>
    </div>
  );
}
