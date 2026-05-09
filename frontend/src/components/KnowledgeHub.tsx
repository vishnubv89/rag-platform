import { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { listDocs, searchDocs, getDoc, getDocTopics } from "../api/client";
import { useChatStore } from "../store/chatStore";
import { useIsMobile } from "../hooks/useIsMobile";
import { KnowledgeMindMap } from "./KnowledgeMindMap";
import type { Doc } from "../types";

function sourceLabel(source: string): string {
  try {
    const host = new URL(source).hostname.replace(/^www\./, "");
    return host;
  } catch {
    return source || "Manual";
  }
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const d = Math.floor(diff / 86400000);
  if (d === 0) return "today";
  if (d === 1) return "yesterday";
  if (d < 30) return `${d}d ago`;
  if (d < 365) return `${Math.floor(d / 30)}mo ago`;
  return `${Math.floor(d / 365)}y ago`;
}

export function KnowledgeHub() {
  const { activeOrg } = useChatStore();
  const orgId = activeOrg?.id ?? null;
  const isMobile = useIsMobile();

  const [query, setQuery] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<"map" | "chunks">("map");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // On mobile, track whether we're showing list or detail
  const showDetail = isMobile ? selectedId !== null : selectedId !== null;
  const showList = isMobile ? selectedId === null : true;

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedQ(query.trim());
      setPage(1);
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query]);

  // Reset selection when org changes
  useEffect(() => { setSelectedId(null); setPage(1); setQuery(""); }, [orgId]);

  // Reset tab to "map" whenever a different document is selected
  useEffect(() => { setActiveTab("map"); }, [selectedId]);

  const listKey = debouncedQ
    ? ["docs-search", orgId, debouncedQ]
    : ["docs-list", orgId, page];

  const { data, isLoading, isError } = useQuery({
    queryKey: listKey,
    queryFn: () =>
      debouncedQ
        ? searchDocs(debouncedQ, orgId)
        : listDocs(orgId, page),
    staleTime: 30_000,
  });

  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ["doc-detail", selectedId],
    queryFn: () => getDoc(selectedId!),
    enabled: selectedId !== null,
    staleTime: 60_000,
  });

  const { data: topicsData, isLoading: topicsLoading } = useQuery({
    queryKey: ["doc-topics", selectedId],
    queryFn: () => getDocTopics(selectedId!),
    enabled: selectedId !== null,
    staleTime: 5 * 60_000,
  });

  const items: Doc[] = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / 20);

  return (
    <div className="flex h-full" style={{ background: "#fafafa" }}>
      {/* Left panel — doc list */}
      {showList && <div
        className="flex flex-col border-r border-gray-100"
        style={{ width: (!isMobile && selectedId) ? 340 : "100%", minWidth: 280, background: "white" }}
      >
        {/* Header */}
        <div className="px-5 pt-5 pb-3 border-b border-gray-100">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-800 text-sm">Knowledge Hub</h2>
            <span className="text-xs text-gray-400">{total.toLocaleString()} docs</span>
          </div>
          <div className="relative">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
              width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2"
            >
              <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
            </svg>
            <input
              type="text"
              placeholder="Search documents…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-300"
            />
            {query && (
              <button
                onClick={() => setQuery("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                ×
              </button>
            )}
          </div>
        </div>

        {/* List body */}
        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <div className="flex items-center justify-center h-32 text-sm text-gray-400">
              Loading…
            </div>
          )}
          {isError && (
            <div className="px-5 py-4 text-sm text-red-500">Failed to load documents.</div>
          )}
          {!isLoading && items.length === 0 && (
            <div className="flex flex-col items-center justify-center h-40 text-sm text-gray-400 gap-1">
              <span>No documents found</span>
              {debouncedQ && <span className="text-xs">Try a different search term</span>}
            </div>
          )}
          {items.map((doc) => (
            <button
              key={doc.id}
              onClick={() => setSelectedId(doc.id === selectedId ? null : doc.id)}
              className="w-full text-left px-5 py-3.5 border-b border-gray-50 hover:bg-indigo-50 transition-colors"
              style={doc.id === selectedId ? { background: "rgba(99,102,241,.07)" } : undefined}
            >
              <div className="flex items-start justify-between gap-2">
                <p
                  className="text-sm font-medium text-gray-800 leading-snug"
                  style={{ wordBreak: "break-word" }}
                >
                  {doc.title}
                </p>
                <span className="text-xs text-gray-400 shrink-0 mt-0.5">{timeAgo(doc.created_at)}</span>
              </div>
              <div className="flex items-center gap-2 mt-1.5">
                {doc.source && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 border border-indigo-100 truncate max-w-[140px]">
                    {sourceLabel(doc.source)}
                  </span>
                )}
                <span className="text-xs text-gray-400">{doc.chunk_count} chunks</span>
              </div>
            </button>
          ))}
        </div>

        {/* Pagination — only for browse mode */}
        {!debouncedQ && totalPages > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100 text-xs text-gray-500">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="px-2 py-1 rounded hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              ← Prev
            </button>
            <span>{page} / {totalPages}</span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="px-2 py-1 rounded hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next →
            </button>
          </div>
        )}
      </div>}

      {/* Right panel — doc detail */}
      {showDetail && (
        <div className="flex-1 flex flex-col overflow-hidden">
          {detailLoading && (
            <div className="flex items-center justify-center h-full text-sm text-gray-400">
              Loading document…
            </div>
          )}
          {detail && !detailLoading && (
            <>
              {/* Detail header */}
              <div className="px-4 pt-4 pb-0 border-b border-gray-100 bg-white shrink-0">
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="flex items-start gap-3 min-w-0">
                    {isMobile && (
                      <button
                        onClick={() => setSelectedId(null)}
                        className="shrink-0 mt-0.5 text-gray-400 hover:text-gray-600"
                        aria-label="Back"
                      >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="15 18 9 12 15 6" />
                        </svg>
                      </button>
                    )}
                    <div className="min-w-0">
                      <h3 className="font-semibold text-gray-900 text-base leading-snug">{detail.title}</h3>
                      <div className="flex items-center gap-3 mt-1 flex-wrap">
                        <span className="text-xs text-gray-400">{detail.chunks.length} chunks</span>
                        <span className="text-xs text-gray-400">{timeAgo(detail.created_at)}</span>
                        {detail.source && (
                          <a href={detail.source} target="_blank" rel="noopener noreferrer"
                             className="text-xs text-indigo-600 hover:text-indigo-800 hover:underline truncate max-w-xs">
                            {sourceLabel(detail.source)} ↗
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                  {!isMobile && (
                    <button onClick={() => setSelectedId(null)}
                            className="shrink-0 text-gray-400 hover:text-gray-600 text-lg leading-none"
                            aria-label="Close">×</button>
                  )}
                </div>

                {/* Tab bar */}
                <div className="flex gap-0">
                  {(["map", "chunks"] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className="px-4 py-2 text-xs font-medium border-b-2 transition-colors"
                      style={{
                        borderBottomColor: activeTab === tab ? "#6366f1" : "transparent",
                        color: activeTab === tab ? "#6366f1" : "#9ca3af",
                      }}
                    >
                      {tab === "map" ? "🗺 Mind Map" : "📄 Chunks"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Tab content */}
              <div className="flex-1 overflow-hidden flex flex-col">
                {activeTab === "map" ? (
                  <KnowledgeMindMap
                    docTitle={detail.title}
                    topics={topicsData?.topics ?? []}
                    isLoading={topicsLoading}
                  />
                ) : (
                  <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
                    {detail.chunks.length === 0 && (
                      <div className="text-sm text-amber-600 bg-amber-50 rounded-xl px-4 py-3 border border-amber-100">
                        ⚠ This document has no chunks — the file may be image-only, encrypted, or embedding failed during upload.
                      </div>
                    )}
                    {detail.chunks.map((chunk) => (
                      <div key={chunk.id} className="rounded-xl p-4 text-sm text-gray-700 leading-relaxed"
                           style={{ background: "white", border: "1px solid #f0f0f0" }}>
                        <div className="text-xs text-gray-400 mb-2 font-mono">chunk {chunk.chunk_index}</div>
                        <p style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{chunk.text}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
