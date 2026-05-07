import { SourceCitations } from "./SourceCitations";
import type { ChatMessage } from "../types";

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
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
          <SourceCitations sources={message.sources} loopCount={message.loopCount} />
        )}
        <div className={`text-xs mt-1.5 ${isUser ? "text-right" : "text-left"}`} style={{ color: "#d1d5db" }}>
          {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </div>
      </div>
    </div>
  );
}
