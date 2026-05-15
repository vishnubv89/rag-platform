/**
 * Interactive knowledge mind map powered by React Flow.
 * Nodes are draggable; the canvas is zoomable and pannable.
 * Three layout modes: Radial · Tree · Sunburst (arc positions only — nodes are always
 * rectangular/circular HTML elements so they remain fully interactive).
 */
import { useState, useCallback, useMemo, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

// ── Types ────────────────────────────────────────────────────────────────────

interface Topic {
  label: string;
  subtopics: string[];
  color: string;
}

interface Props {
  docTitle: string;
  topics: Topic[];
  isLoading?: boolean;
}

type Layout = "radial" | "tree" | "sunburst";

// ── Custom node components ────────────────────────────────────────────────────

function CenterNodeComp({ data }: NodeProps) {
  return (
    <div
      style={{
        width: 96, height: 96, borderRadius: "50%",
        background: "linear-gradient(135deg,#1e293b,#334155)",
        boxShadow: "0 4px 20px rgba(0,0,0,.35)",
        display: "flex", alignItems: "center", justifyContent: "center",
        textAlign: "center", padding: 10, cursor: "grab",
        border: "2px solid #475569",
      }}
    >
      <span style={{ fontSize: 10, fontWeight: 700, color: "#fff", lineHeight: 1.3 }}>
        {String(data.label)}
      </span>
    </div>
  );
}

function TopicNodeComp({ data, selected }: NodeProps) {
  const color = String(data.color ?? "#6366f1");
  return (
    <div
      style={{
        width: 84, height: 84, borderRadius: "50%",
        border: `2.5px solid ${color}`,
        background: `${color}18`,
        boxShadow: selected ? `0 0 0 3px ${color}44` : `0 2px 8px ${color}22`,
        display: "flex", alignItems: "center", justifyContent: "center",
        textAlign: "center", padding: 8, cursor: "grab",
        transition: "box-shadow .15s",
      }}
    >
      <span style={{ fontSize: 10, fontWeight: 700, color, lineHeight: 1.3 }}>
        {String(data.label)}
      </span>
    </div>
  );
}

function SubtopicNodeComp({ data }: NodeProps) {
  const color = String(data.color ?? "#6366f1");
  return (
    <div
      style={{
        padding: "5px 10px", borderRadius: 20,
        background: "#fff",
        border: `1.5px solid ${color}55`,
        boxShadow: "0 1px 4px rgba(0,0,0,.07)",
        cursor: "grab", whiteSpace: "nowrap",
      }}
    >
      <span style={{ fontSize: 10, color: "#475569", fontWeight: 500 }}>
        {String(data.label)}
      </span>
    </div>
  );
}

const nodeTypes = {
  center:   CenterNodeComp,
  topic:    TopicNodeComp,
  subtopic: SubtopicNodeComp,
};

// ── Layout builders ───────────────────────────────────────────────────────────

function buildRadial(topics: Topic[], docTitle: string) {
  const cx = 500, cy = 340, R1 = 200, R2 = 110;
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  nodes.push({
    id: "center", type: "center",
    position: { x: cx - 48, y: cy - 48 },
    data: { label: docTitle.replace(/\.[^.]+$/, "").slice(0, 22) },
    draggable: true,
  });

  topics.forEach((t, i) => {
    const a  = (i / topics.length) * 2 * Math.PI - Math.PI / 2;
    const tx = cx + R1 * Math.cos(a);
    const ty = cy + R1 * Math.sin(a);
    const tid = `topic-${i}`;

    nodes.push({
      id: tid, type: "topic",
      position: { x: tx - 42, y: ty - 42 },
      data: { label: t.label, color: t.color },
      draggable: true,
    });

    edges.push({
      id: `e-c-${tid}`, source: "center", target: tid,
      style: { stroke: t.color, strokeWidth: 2, opacity: .45 },
      type: "straight",
    });

    const n = t.subtopics.length;
    t.subtopics.forEach((s, j) => {
      const sa = a + (j - (n - 1) / 2) * 0.42;
      const sid = `sub-${i}-${j}`;
      nodes.push({
        id: sid, type: "subtopic",
        position: { x: tx + R2 * Math.cos(sa) - 36, y: ty + R2 * Math.sin(sa) - 14 },
        data: { label: s, color: t.color },
        draggable: true,
      });
      edges.push({
        id: `e-${tid}-${sid}`, source: tid, target: sid,
        style: { stroke: t.color, strokeWidth: 1.3, opacity: .3 },
        type: "straight",
      });
    });
  });

  return { nodes, edges };
}

function buildTree(topics: Topic[], docTitle: string) {
  const W = 1000, rootY = 80, topicY = 260, subY = 440;
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const colW = W / (topics.length + 1);

  nodes.push({
    id: "center", type: "center",
    position: { x: W / 2 - 48, y: rootY },
    data: { label: docTitle.replace(/\.[^.]+$/, "").slice(0, 22) },
    draggable: true,
  });

  topics.forEach((t, i) => {
    const tx = colW * (i + 1);
    const tid = `topic-${i}`;
    nodes.push({
      id: tid, type: "topic",
      position: { x: tx - 42, y: topicY },
      data: { label: t.label, color: t.color },
      draggable: true,
    });
    edges.push({
      id: `e-c-${tid}`, source: "center", target: tid,
      style: { stroke: t.color, strokeWidth: 2, opacity: .4 },
      type: "smoothstep",
    });

    const n = t.subtopics.length;
    const spread = Math.min(colW * .9, 130);
    t.subtopics.forEach((s, j) => {
      const sx = tx + (j - (n - 1) / 2) * (n > 1 ? spread / (n - 1) : 0);
      const sid = `sub-${i}-${j}`;
      nodes.push({
        id: sid, type: "subtopic",
        position: { x: sx - 36, y: subY },
        data: { label: s, color: t.color },
        draggable: true,
      });
      edges.push({
        id: `e-${tid}-${sid}`, source: tid, target: sid,
        style: { stroke: t.color, strokeWidth: 1.3, opacity: .3 },
        type: "smoothstep",
      });
    });
  });

  return { nodes, edges };
}

function buildSunburst(topics: Topic[], docTitle: string) {
  // Sunburst is tricky with HTML nodes — we lay topics out like a wheel
  // with subtopics further out, all still draggable.
  const cx = 500, cy = 360, R1 = 190, R2 = 320;
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  nodes.push({
    id: "center", type: "center",
    position: { x: cx - 48, y: cy - 48 },
    data: { label: docTitle.replace(/\.[^.]+$/, "").slice(0, 22) },
    draggable: true,
  });

  // Each topic gets an equal arc slice; subtopics fan within that arc
  topics.forEach((t, i) => {
    const sliceAngle = (2 * Math.PI) / topics.length;
    const ta = -Math.PI / 2 + (i + 0.5) * sliceAngle;
    const tx = cx + R1 * Math.cos(ta);
    const ty = cy + R1 * Math.sin(ta);
    const tid = `topic-${i}`;

    nodes.push({
      id: tid, type: "topic",
      position: { x: tx - 42, y: ty - 42 },
      data: { label: t.label, color: t.color },
      draggable: true,
    });
    edges.push({
      id: `e-c-${tid}`, source: "center", target: tid,
      style: { stroke: t.color, strokeWidth: 2, opacity: .4 },
      type: "straight",
    });

    const n = t.subtopics.length;
    t.subtopics.forEach((s, j) => {
      const sa = ta + (j - (n - 1) / 2) * 0.35;
      const sx = cx + R2 * Math.cos(sa);
      const sy = cy + R2 * Math.sin(sa);
      const sid = `sub-${i}-${j}`;
      nodes.push({
        id: sid, type: "subtopic",
        position: { x: sx - 36, y: sy - 14 },
        data: { label: s, color: t.color },
        draggable: true,
      });
      edges.push({
        id: `e-${tid}-${sid}`, source: tid, target: sid,
        style: { stroke: t.color, strokeWidth: 1.3, opacity: .3 },
        type: "straight",
      });
    });
  });

  return { nodes, edges };
}

function buildGraph(layout: Layout, topics: Topic[], docTitle: string) {
  if (layout === "tree")     return buildTree(topics, docTitle);
  if (layout === "sunburst") return buildSunburst(topics, docTitle);
  return buildRadial(topics, docTitle);
}

// ── Main component ────────────────────────────────────────────────────────────

export function KnowledgeMindMap({ docTitle, topics, isLoading }: Props) {
  const [layout, setLayout] = useState<Layout>("radial");

  const initial = useMemo(
    () => buildGraph(layout, topics, docTitle),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [] // computed once on mount; layout changes handled by resetLayout below
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);

  // Rebuild graph when layout or topics change
  useEffect(() => {
    const { nodes: n, edges: e } = buildGraph(layout, topics, docTitle);
    setNodes(n);
    setEdges(e);
  }, [layout, topics, docTitle, setNodes, setEdges]);

  const switchLayout = useCallback((l: Layout) => setLayout(l), []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400 gap-2">
        <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="31.4" strokeDashoffset="10" />
        </svg>
        Extracting topics…
      </div>
    );
  }

  if (!topics.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-sm text-gray-400 gap-2">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2z" />
          <path d="M12 8v4m0 4h.01" />
        </svg>
        <span>No topics extracted for this document</span>
        <span className="text-xs">(document may have no chunks)</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Layout toggle */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-gray-100 bg-white shrink-0">
        <span className="text-xs text-gray-400 font-medium mr-1">Layout</span>
        {(["radial", "tree", "sunburst"] as Layout[]).map((l) => (
          <button
            key={l}
            onClick={() => switchLayout(l)}
            className="px-3 py-1 rounded-full text-xs font-medium transition-colors"
            style={{
              background: layout === l ? "#6366f1" : "#f3f4f6",
              color:      layout === l ? "#fff"     : "#6b7280",
            }}
          >
            {l === "radial" ? "⬤ Radial" : l === "tree" ? "⊤ Tree" : "◎ Sunburst"}
          </button>
        ))}
        <span className="ml-auto text-xs text-gray-300">drag nodes · scroll to zoom</span>
      </div>

      {/* React Flow canvas */}
      <div className="flex-1 relative" style={{ background: "#fafbfc" }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.25 }}
          minZoom={0.3}
          maxZoom={2.5}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#e5e7eb" gap={24} size={1} />
          <Controls
            showInteractive={false}
            style={{ bottom: 16, left: 16, top: "unset" }}
          />
        </ReactFlow>

        {/* Topic legend overlay */}
        <div
          className="absolute top-3 right-3 flex flex-col gap-1.5 pointer-events-none"
          style={{ maxWidth: 160 }}
        >
          {topics.map((t) => (
            <div key={t.label} className="flex items-center gap-1.5">
              <span
                style={{
                  width: 10, height: 10, borderRadius: "50%",
                  background: t.color, flexShrink: 0,
                }}
              />
              <span style={{ fontSize: 10, color: "#374151", lineHeight: 1.2 }}>
                {t.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
