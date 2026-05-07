import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Sidebar } from "./components/Sidebar";
import { ChatWindow } from "./components/ChatWindow";
import { ComingSoon } from "./components/ComingSoon";
import { KnowledgeHub } from "./components/KnowledgeHub";
import { DocCreator } from "./components/DocCreator";
import { Analytics } from "./components/Analytics";
import { OrgSelector } from "./components/OrgSelector";
import { useChatStore } from "./store/chatStore";

const queryClient = new QueryClient();

type App = "chat" | "knowledge" | "creator" | "search" | "analytics";

const APP_LABELS: Record<App, string> = {
  chat:      "Chat",
  knowledge: "Knowledge Hub",
  creator:   "Doc Creator",
  search:    "Visual Search",
  analytics: "Analytics",
};

function Portal() {
  const [activeApp, setActiveApp] = useState<App>("chat");
  const { newSession } = useChatStore();

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar activeApp={activeApp} onAppChange={setActiveApp} />

      <div className="flex flex-col flex-1 min-w-0" style={{ background: "#f7f7f8" }}>
        {/* Top bar */}
        <header
          className="flex items-center justify-between px-6 flex-shrink-0"
          style={{ height: 48, background: "#ffffff", borderBottom: "1px solid #e8e8ea" }}
        >
          <div className="flex items-center gap-2">
            <span className="font-semibold text-gray-800 text-sm tracking-tight">
              {APP_LABELS[activeApp]}
            </span>
            <span
              className="text-xs px-1.5 py-0.5 rounded"
              style={{ background: "#f3f4f6", color: "#9ca3af", fontSize: ".6rem", letterSpacing: ".06em" }}
            >
              BETA
            </span>
          </div>

          <div className="flex items-center gap-3">
            {activeApp === "chat" && (
              <button
                onClick={newSession}
                className="text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
                style={{ background: "#f3f4f6", color: "#374151" }}
                onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "#e5e7eb")}
                onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "#f3f4f6")}
              >
                New chat
              </button>
            )}
            <OrgSelector />
          </div>
        </header>

        {/* App content */}
        <main className="flex-1 overflow-hidden">
          {activeApp === "chat"      && <ChatWindow />}
          {activeApp === "knowledge" && <KnowledgeHub />}
          {activeApp === "creator"   && <DocCreator />}
          {activeApp === "search"    && (
            <ComingSoon
              name="Visual Search"
              description="Search across images, diagrams, and screenshots using vision models."
              features={["Image similarity search", "OCR extraction", "Diagram indexing", "Screenshot search", "Multi-modal retrieval", "Source preview"]}
            />
          )}
          {activeApp === "analytics" && <Analytics />}
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Portal />
    </QueryClientProvider>
  );
}
