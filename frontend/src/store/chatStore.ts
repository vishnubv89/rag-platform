import { create } from "zustand";
import { persist } from "zustand/middleware";
import { v4 as uuidv4 } from "uuid";
import type { ChatMessage, Org, Session } from "../types";

interface ChatStore {
  messages: ChatMessage[];
  sessions: Session[];
  activeSessionId: string;
  activeOrg: Org | null;
  sessionId: string;

  addMessage: (msg: ChatMessage) => void;
  newSession: () => void;
  loadSession: (sessionId: string, messages?: ChatMessage[]) => void;
  setOrg: (org: Org | null) => void;
  saveCurrentSession: () => void;
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      messages: [],
      sessions: [],
      activeSessionId: uuidv4(),
      activeOrg: null,
      sessionId: uuidv4(),

      addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

      newSession: () => {
        get().saveCurrentSession();
        set({ messages: [], sessionId: uuidv4(), activeSessionId: uuidv4() });
      },

      loadSession: (id, messages?) => {
        get().saveCurrentSession();
        // If messages provided directly (from API), use them; else fall back to localStorage
        const resolved = messages ?? get().sessions.find((s) => s.id === id)?.messages ?? [];
        set({ messages: resolved, activeSessionId: id, sessionId: id });
      },

      setOrg: (org) => set({ activeOrg: org }),

      saveCurrentSession: () => {
        const { messages, activeSessionId, sessions } = get();
        if (messages.length === 0) return;
        const preview = messages.find((m) => m.role === "user")?.content ?? "";
        const existing = sessions.findIndex((s) => s.id === activeSessionId);
        const updated: Session = {
          id: activeSessionId,
          preview: preview.slice(0, 60),
          messages,
          orgId: get().activeOrg?.id ?? null,
        };
        if (existing >= 0) {
          const next = [...sessions];
          next[existing] = updated;
          set({ sessions: next });
        } else {
          set({ sessions: [updated, ...sessions].slice(0, 50) });
        }
      },
    }),
    { name: "rag-chat-store", partialize: (s) => ({ sessions: s.sessions }) }
  )
);
