import { useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { sendChatStream, getFollowUps } from "../api/client";
import { useChatStore } from "../store/chatStore";
import type { ChatMessage } from "../types";

export function useChat() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [streamingContent, setStreamingContent] = useState<string>("");
  const { messages, activeOrg, sessionId, addMessage } = useChatStore();

  async function send(text: string) {
    if (!text.trim() || loading) return;
    setError(null);
    setSuggestions([]);
    setStreamingContent("");

    const userMsg: ChatMessage = {
      id: uuidv4(),
      role: "user",
      content: text.trim(),
      sourceChunkIds: [],
      sources: [],
      loopCount: 0,
      timestamp: new Date(),
    };
    addMessage(userMsg);
    setLoading(true);

    let accumulated = "";

    try {
      for await (const event of sendChatStream(
        text.trim(),
        messages,
        activeOrg?.id ?? null,
        sessionId,
      )) {
        if (event.type === "token") {
          accumulated += event.content;
          setStreamingContent(accumulated);
        } else if (event.type === "done") {
          setStreamingContent("");
          const assistantMsg: ChatMessage = {
            id: uuidv4(),
            role: "assistant",
            content: event.answer,
            sourceChunkIds: event.source_chunk_ids,
            sources: event.sources ?? [],
            loopCount: event.loop_count,
            timestamp: new Date(),
            logId: event.log_id ?? undefined,
          };
          addMessage(assistantMsg);

          const history = [
            ...messages,
            { role: "user", content: text.trim() },
            { role: "assistant", content: event.answer },
          ].map((m) => ({ role: m.role, content: m.content }));
          getFollowUps(history, activeOrg?.id ?? null)
            .then(setSuggestions)
            .catch(() => {/* silently skip */});
        } else if (event.type === "error") {
          setError(event.message);
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
      setStreamingContent("");
    }
  }

  return { send, loading, error, suggestions, streamingContent };
}
