import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { SourceCitations } from "./SourceCitations";
import { submitFeedback } from "../api/client";
import type { ChatMessage } from "../types";

interface Props {
  message: ChatMessage;
}

/** Renders assistant markdown responses with proper visual hierarchy. */
export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const [feedback, setFeedback] = useState<1 | -1 | null>(message.feedback ?? null);

  async function handleFeedback(value: 1 | -1) {
    if (feedback !== null || !message.logId) return;
    setFeedback(value);
    try {
      await submitFeedback(message.logId, value);
    } catch {
      setFeedback(null);
    }
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-5`}>
      <div className={`max-w-[72%] ${isUser ? "order-2" : "order-1"}`}>
        <div
          className="px-4 py-3 rounded-2xl text-sm leading-relaxed"
          style={
            isUser
              ? { background: "#18181b", color: "#f9fafb", borderRadius: "16px 16px 4px 16px", whiteSpace: "pre-wrap" }
              : { background: "#ffffff", color: "#111827", border: "1px solid #e8e8ea", borderRadius: "4px 16px 16px 16px" }
          }
        >
          {isUser ? (
            message.content
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                // Headings
                h1: ({ children }) => (
                  <h1 className="text-base font-bold mt-3 mb-1 first:mt-0" style={{ color: "#111827" }}>{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-sm font-bold mt-3 mb-1 first:mt-0" style={{ color: "#111827" }}>{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-sm font-semibold mt-2 mb-1 first:mt-0" style={{ color: "#374151" }}>{children}</h3>
                ),
                // Paragraphs
                p: ({ children }) => (
                  <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>
                ),
                // Bold & italic
                strong: ({ children }) => (
                  <strong className="font-semibold" style={{ color: "#111827" }}>{children}</strong>
                ),
                em: ({ children }) => (
                  <em className="italic" style={{ color: "#374151" }}>{children}</em>
                ),
                // Bullet lists
                ul: ({ children }) => (
                  <ul className="my-2 space-y-1 pl-4" style={{ listStyleType: "disc" }}>{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="my-2 space-y-1 pl-4" style={{ listStyleType: "decimal" }}>{children}</ol>
                ),
                li: ({ children }) => (
                  <li className="leading-relaxed pl-1">{children}</li>
                ),
                // Inline code
                code: ({ children, className }) => {
                  const isBlock = className?.startsWith("language-");
                  return isBlock ? (
                    <code className={className}>{children}</code>
                  ) : (
                    <code
                      className="px-1.5 py-0.5 rounded text-xs font-mono"
                      style={{ background: "#f3f4f6", color: "#6366f1", border: "1px solid #e5e7eb" }}
                    >
                      {children}
                    </code>
                  );
                },
                // Code blocks
                pre: ({ children }) => (
                  <pre
                    className="my-2 p-3 rounded-lg text-xs font-mono overflow-x-auto leading-relaxed"
                    style={{ background: "#1e1e2e", color: "#cdd6f4", border: "1px solid #313244" }}
                  >
                    {children}
                  </pre>
                ),
                // Blockquotes
                blockquote: ({ children }) => (
                  <blockquote
                    className="my-2 pl-3 italic text-xs"
                    style={{ borderLeft: "3px solid #6366f1", color: "#6b7280" }}
                  >
                    {children}
                  </blockquote>
                ),
                // Horizontal rule
                hr: () => <hr className="my-3" style={{ borderColor: "#e5e7eb" }} />,
                // Tables (via remark-gfm)
                table: ({ children }) => (
                  <div className="my-2 overflow-x-auto">
                    <table className="w-full text-xs border-collapse">{children}</table>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead style={{ background: "#f9fafb" }}>{children}</thead>
                ),
                th: ({ children }) => (
                  <th
                    className="px-3 py-1.5 text-left font-semibold"
                    style={{ border: "1px solid #e5e7eb", color: "#374151" }}
                  >
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="px-3 py-1.5" style={{ border: "1px solid #e5e7eb" }}>{children}</td>
                ),
                // Links
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline"
                    style={{ color: "#6366f1" }}
                  >
                    {children}
                  </a>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          )}
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
