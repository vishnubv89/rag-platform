import { useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { sendChat, getFollowUps } from "../api/client";
import { useChatStore } from "../store/chatStore";
import type { ChatMessage } from "../types";

export function useChat() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const { messages, activeOrg, sessionId, addMessage } = useChatStore();

  async function send(text: string) {
    if (!text.trim() || loading) return;
    setError(null);
    setSuggestions([]);

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

    try {
      const res = await sendChat(text.trim(), messages, activeOrg?.id ?? null, sessionId);
      const assistantMsg: ChatMessage = {
        id: uuidv4(),
        role: "assistant",
        content: res.answer,
        sourceChunkIds: res.source_chunk_ids,
        sources: res.sources ?? [],
        loopCount: res.loop_count,
        timestamp: new Date(),
      };
      addMessage(assistantMsg);

      // Fetch follow-up suggestions asynchronously — don't block the response
      const history = [
        ...messages,
        { role: "user", content: text.trim() },
        { role: "assistant", content: res.answer },
      ].map((m) => ({ role: m.role, content: m.content }));
      getFollowUps(history, activeOrg?.id ?? null)
        .then(setSuggestions)
        .catch(() => {/* silently skip if suggestions fail */});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return { send, loading, error, suggestions };
}
