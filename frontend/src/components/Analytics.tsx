import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useChatStore } from "../store/chatStore";
import {
  getAnalyticsSummary,
  getAnalyticsLogs,
  getTopSources,
  getTopicGraph,
} from "../api/client";

// ─── helpers ────────────────────────────────────────────────────────────────

function fmt(n: number | undefined, unit = "") {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M${unit}`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k${unit}`;
  return `${n}${unit}`;
}

function timeAgo(iso: string) {
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (d < 1) return "just now";
  if (d < 60) return `${d}m ago`;
  if (d < 1440) return `${Math.floor(d / 60)}h ago`;
  return `${Math.floor(d / 1440)}d ago`;
}

// ─── sub-components ──────────────────────────────────────────────────────────

function Card({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl p-5" style={{ background: "white", border: "1px solid #f0f0f0" }}>
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

function BarChart({ data }: { data: { label: string; value: number }[] }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="space-y-2">
      {data.map((d) => (
        <div key={d.label} className="flex items-center gap-3">
          <span className="text-xs text-gray-500 truncate" style={{ width: 160, minWidth: 160 }}>
            {d.label}
          </span>
          <div className="flex-1 h-5 rounded-full overflow-hidden" style={{ background: "#f3f4f6" }}>
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${(d.value / max) * 100}%`,
                background: "linear-gradient(90deg,#6366f1,#818cf8)",
                minWidth: d.value ? 8 : 0,
              }}
            />
          </div>
          <span className="text-xs font-medium text-gray-600 w-8 text-right">{d.value}</span>
        </div>
      ))}
      {data.length === 0 && (
        <p className="text-sm text-gray-400 py-4 text-center">No data yet</p>
      )}
    </div>
  );
}

function DailyChart({ data }: { data: { day: string; chats: number }[] }) {
  const max = Math.max(...data.map((d) => d.chats), 1);
  return (
    <div className="flex items-end gap-1 h-20">
      {data.length === 0 && (
        <p className="text-sm text-gray-400 w-full text-center self-center">No data yet</p>
      )}
      {data.map((d) => (
        <div key={d.day} className="flex-1 flex flex-col items-center gap-1" title={`${d.day}: ${d.chats} chats`}>
          <div
            className="w-full rounded-t"
            style={{
              height: `${Math.max((d.chats / max) * 64, d.chats ? 4 : 0)}px`,
              background: "linear-gradient(180deg,#6366f1,#818cf8)",
            }}
          />
          <span className="text-gray-300" style={{ fontSize: 9 }}>
            {d.day.slice(5)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Topic graph ─────────────────────────────────────────────────────────────

const COLORS = ["#6366f1","#8b5cf6","#06b6d4","#10b981","#f59e0b","#ef4444","#ec4899","#14b8a6"];

function TopicGraph({ orgId, days }: { orgId: number | null; days: number }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["topic-graph", orgId, days],
    queryFn: () => getTopicGraph(orgId, days),
    staleTime: 60_000,
  });

  const buildFlow = useCallback(() => {
    if (!data?.nodes.length) return { nodes: [], edges: [] };

    const maxCit = Math.max(...data.nodes.map((n) => n.citations), 1);
    const cx = 500, cy = 300, r = 220;
    const flowNodes: Node[] = data.nodes.map((n, i) => {
      const angle = (2 * Math.PI * i) / data.nodes.length - Math.PI / 2;
      const size = 36 + (n.citations / maxCit) * 48;
      return {
        id: String(n.id),
        position: { x: cx + r * Math.cos(angle) - size / 2, y: cy + r * Math.sin(angle) - size / 2 },
        data: { label: n.title },
        style: {
          background: COLORS[i % COLORS.length],
          color: "white",
          borderRadius: 12,
          padding: "6px 10px",
          fontSize: 11,
          fontWeight: 600,
          border: "none",
          width: Math.max(size * 2.5, 120),
          textAlign: "center" as const,
          boxShadow: "0 2px 8px rgba(0,0,0,.12)",
        },
      };
    });

    const maxW = Math.max(...data.edges.map((e) => e.weight), 1);
    const flowEdges: Edge[] = data.edges.map((e) => ({
      id: `${e.source}-${e.target}`,
      source: String(e.source),
      target: String(e.target),
      style: { stroke: "#c7d2fe", strokeWidth: 1 + (e.weight / maxW) * 4 },
      animated: e.weight >= maxW * 0.6,
    }));

    return { nodes: flowNodes, edges: flowEdges };
  }, [data]);

  const { nodes: initNodes, edges: initEdges } = buildFlow();
  const [nodes, , onNodesChange] = useNodesState(initNodes);
  const [edges, , onEdgesChange] = useEdgesState(initEdges);

  if (isLoading) return <div className="flex items-center justify-center h-full text-sm text-gray-400">Loading…</div>;
  if (isError) return <div className="flex items-center justify-center h-full text-sm text-red-400">Failed to load graph</div>;
  if (!data?.nodes.length) return (
    <div className="flex flex-col items-center justify-center h-full gap-2">
      <p className="text-sm text-gray-400">No data yet</p>
      <p className="text-xs text-gray-300">Topic connections appear once users start chatting</p>
    </div>
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      attributionPosition="bottom-left"
    >
      <Background color="#f3f4f6" gap={20} />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}

// ─── Main ────────────────────────────────────────────────────────────────────

export function Analytics() {
  const { activeOrg } = useChatStore();
  const orgId = activeOrg?.id ?? null;
  const [days, setDays] = useState(30);
  const [logPage, setLogPage] = useState(1);

  const { data: summary } = useQuery({
    queryKey: ["analytics-summary", orgId, days],
    queryFn: () => getAnalyticsSummary(orgId),
    staleTime: 30_000,
  });

  const { data: logsData } = useQuery({
    queryKey: ["analytics-logs", orgId, logPage],
    queryFn: () => getAnalyticsLogs(orgId, logPage),
    staleTime: 30_000,
  });

  const { data: topSources } = useQuery({
    queryKey: ["top-sources", orgId, days],
    queryFn: () => getTopSources(orgId, days),
    staleTime: 60_000,
  });

  const { data: tokenUsage } = useQuery({
    queryKey: ["token-usage", orgId, days],
    queryFn: async () => {
      const p = new URLSearchParams({ days: String(days) });
      if (orgId) p.set("org_id", String(orgId));
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}/admin/analytics/token-usage?${p}`, {
        headers: { "X-Admin-Key": import.meta.env.VITE_ADMIN_KEY ?? "change-me" },
      });
      return res.json() as Promise<{ day: string; chats: number; prompt_tokens: number; completion_tokens: number }[]>;
    },
    staleTime: 60_000,
  });

  const totalLogs = logsData?.total ?? 0;
  const totalLogPages = Math.ceil(totalLogs / 15);

  return (
    <div className="h-full overflow-y-auto" style={{ background: "#fafafa" }}>
      <div className="max-w-6xl mx-auto px-6 py-6 space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-gray-800">Analytics</h2>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white text-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-2 gap-4" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>
          <Card label="Total queries" value={fmt(summary?.total_chats)} />
          <Card label="Avg latency" value={fmt(summary?.avg_latency_ms, "ms")} />
          <Card label="Prompt tokens" value={fmt(summary?.total_prompt_tokens)} />
          <Card label="Completion tokens" value={fmt(summary?.total_completion_tokens)} />
        </div>

        {/* Charts row */}
        <div className="grid gap-4" style={{ gridTemplateColumns: "1fr 1fr" }}>
          {/* Daily activity */}
          <div className="rounded-2xl p-5" style={{ background: "white", border: "1px solid #f0f0f0" }}>
            <p className="text-sm font-semibold text-gray-700 mb-4">Daily queries</p>
            <DailyChart data={(tokenUsage ?? []).map((d) => ({ day: String(d.day), chats: d.chats }))} />
          </div>

          {/* Top sources */}
          <div className="rounded-2xl p-5" style={{ background: "white", border: "1px solid #f0f0f0" }}>
            <p className="text-sm font-semibold text-gray-700 mb-4">Top cited sources</p>
            <BarChart
              data={(topSources ?? []).map((s) => ({ label: s.title, value: s.citation_count }))}
            />
          </div>
        </div>

        {/* Topic mind map */}
        <div className="rounded-2xl overflow-hidden" style={{ background: "white", border: "1px solid #f0f0f0", height: 420 }}>
          <div className="px-5 py-3.5 border-b border-gray-100 flex items-center justify-between">
            <p className="text-sm font-semibold text-gray-700">Topic connections</p>
            <span className="text-xs text-gray-400">Node size = citations · Line thickness = co-occurrence</span>
          </div>
          <div style={{ height: 372 }}>
            <TopicGraph orgId={orgId} days={days} />
          </div>
        </div>

        {/* Query log */}
        <div className="rounded-2xl overflow-hidden" style={{ background: "white", border: "1px solid #f0f0f0" }}>
          <div className="px-5 py-3.5 border-b border-gray-100 flex items-center justify-between">
            <p className="text-sm font-semibold text-gray-700">Recent queries</p>
            <span className="text-xs text-gray-400">{totalLogs.toLocaleString()} total</span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid #f3f4f6" }}>
                {["Query", "Loops", "Latency", "Tokens", "When"].map((h) => (
                  <th key={h} className="px-5 py-2.5 text-left text-xs font-medium text-gray-400">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(logsData?.items ?? []).map((row) => (
                <tr key={String(row.id)} style={{ borderBottom: "1px solid #f9fafb" }}>
                  <td className="px-5 py-3 text-gray-700 max-w-xs truncate">{String(row.user_message)}</td>
                  <td className="px-5 py-3 text-gray-500">{String(row.loop_count ?? 0)}</td>
                  <td className="px-5 py-3 text-gray-500">{row.latency_ms != null ? `${row.latency_ms}ms` : "—"}</td>
                  <td className="px-5 py-3 text-gray-500">
                    {row.prompt_tokens != null ? `${fmt(Number(row.prompt_tokens))} / ${fmt(Number(row.completion_tokens))}` : "—"}
                  </td>
                  <td className="px-5 py-3 text-gray-400 whitespace-nowrap">{timeAgo(String(row.created_at))}</td>
                </tr>
              ))}
              {!logsData?.items?.length && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-sm text-gray-400">No queries yet</td>
                </tr>
              )}
            </tbody>
          </table>
          {totalLogPages > 1 && (
            <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100 text-xs text-gray-500">
              <button disabled={logPage <= 1} onClick={() => setLogPage((p) => p - 1)}
                className="px-2 py-1 rounded hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed">← Prev</button>
              <span>{logPage} / {totalLogPages}</span>
              <button disabled={logPage >= totalLogPages} onClick={() => setLogPage((p) => p + 1)}
                className="px-2 py-1 rounded hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed">Next →</button>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
