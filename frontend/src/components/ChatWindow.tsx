import { useEffect, useRef, useState } from "react";
import { MessageBubble } from "./MessageBubble";
import { MessageInput } from "./MessageInput";
import { FileUpload } from "./FileUpload";
import { useChat } from "../hooks/useChat";
import { useChatStore } from "../store/chatStore";

export function ChatWindow() {
  const { messages } = useChatStore();
  const { send, loading, error } = useChat();
  const [showUpload, setShowUpload] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <div className="text-5xl mb-4">🧠</div>
            <p className="text-lg font-medium">Ask anything</p>
            <p className="text-sm mt-1">Or drop a document below to add it to the knowledge base</p>
          </div>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        {error && (
          <div className="text-center text-red-500 text-sm py-2">{error}</div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* File upload toggle */}
      <div className="px-4 pb-1 flex justify-end">
        <button
          onClick={() => setShowUpload((v) => !v)}
          className="text-xs text-gray-400 hover:text-indigo-500 transition-colors"
        >
          {showUpload ? "Hide upload" : "📎 Upload document"}
        </button>
      </div>
      {showUpload && <FileUpload />}

      <MessageInput onSend={send} loading={loading} />
    </div>
  );
}
