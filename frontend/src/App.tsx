import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChatWindow } from "./components/ChatWindow";
import { HistoryPanel } from "./components/HistoryPanel";
import { OrgSelector } from "./components/OrgSelector";

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex h-screen bg-gray-50 font-sans">
        <HistoryPanel />
        <div className="flex flex-col flex-1 min-w-0">
          <header className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-100 shadow-sm">
            <div className="flex items-center gap-2">
              <span className="text-xl">🧠</span>
              <span className="font-semibold text-gray-800">RAG Chat</span>
            </div>
            <OrgSelector />
          </header>
          <main className="flex-1 overflow-hidden">
            <ChatWindow />
          </main>
        </div>
      </div>
    </QueryClientProvider>
  );
}

export default App
