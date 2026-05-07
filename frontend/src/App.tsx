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

const APP_META: Record<App, { label: string; icon: string }> = {
  chat:      { label: "Chat",           icon: "💬" },
  knowledge: { label: "Knowledge Hub",  icon: "📚" },
  creator:   { label: "Doc Creator",    icon: "✏️"  },
  search:    { label: "Visual Search",  icon: "🖼️" },
  analytics: { label: "Analytics",      icon: "📊" },
};

function Portal() {
  const [activeApp, setActiveApp] = useState<App>("chat");
  const { newSession } = useChatStore();

  const meta = APP_META[activeApp];

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar activeApp={activeApp} onAppChange={setActiveApp} />

      <div className="flex flex-col flex-1 min-w-0" style={{ background: "#ffffff" }}>
        {/* Top bar */}
        <header
          className="flex items-center justify-between px-6"
          style={{
            height: 52,
            minHeight: 52,
            borderBottom: "1px solid #f0f0f0",
            background: "white",
          }}
        >
          <div className="flex items-center gap-2">
            <span className="text-base leading-none">{meta.icon}</span>
            <span className="font-semibold text-gray-800 text-sm">{meta.label}</span>
            <span
              className="text-xs px-1.5 py-0.5 rounded"
              style={{ background: "#f3f4f6", color: "#9ca3af", fontSize: ".65rem", letterSpacing: ".05em" }}
            >
              BETA
            </span>
          </div>

          <div className="flex items-center gap-3">
            {activeApp === "chat" && (
              <button
                onClick={newSession}
                className="text-sm px-3 py-1.5 rounded-lg transition-colors font-medium"
                style={{ background: "#f3f4f6", color: "#374151" }}
                onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "#e5e7eb")}
                onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "#f3f4f6")}
              >
                + New chat
              </button>
            )}
            <OrgSelector />
          </div>
        </header>

        {/* App content */}
        <main className="flex-1 overflow-hidden">
          {activeApp === "chat" && <ChatWindow />}

          {activeApp === "knowledge" && <KnowledgeHub />}

          {activeApp === "creator" && <DocCreator />}

          {activeApp === "search" && (
            <ComingSoon
              icon="🖼️"
              name="Visual Search"
              description="Search across images, diagrams, and screenshots embedded in your documents using vision models."
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
