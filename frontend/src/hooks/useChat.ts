import { useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { sendChat } from "../api/client";
import { useChatStore } from "../store/chatStore";
import type { ChatMessage } from "../types";

export function useChat() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { messages, activeOrg, sessionId, addMessage } = useChatStore();

  async function send(text: string) {
    if (!text.trim() || loading) return;
    setError(null);

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
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return { send, loading, error };
}
