import { useEffect, useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type NodeProps,
} from "reactflow";
import "reactflow/dist/style.css";
import { useNavigate } from "react-router-dom";
import type { EntityGraphResponse } from "@/hooks/use-entities";

const TYPE_BG: Record<string, string> = {
  person: "#fecdd3",
  org: "#e9d5ff",
  concept: "#bae6fd",
  tool: "#a7f3d0",
  product: "#fde68a",
  event: "#f5d0fe",
  location: "#99f6e4",
  other: "#e5e7eb",
};

const TYPE_BORDER: Record<string, string> = {
  person: "#fb7185",
  org: "#a855f7",
  concept: "#0ea5e9",
  tool: "#10b981",
  product: "#f59e0b",
  event: "#d946ef",
  location: "#14b8a6",
  other: "#9ca3af",
};

interface EntityNodeData {
  name: string;
  size: number;
  bg: string;
  border: string;
  fontSize: number;
  hasSynthesis: boolean;
}

function EntityNode({ data }: NodeProps<EntityNodeData>) {
  return (
    <div
      style={{
        width: data.size,
        height: data.size,
        borderRadius: "50%",
        background: data.bg,
        border: `2px solid ${data.border}`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: data.fontSize,
        color: "#111",
        textAlign: "center",
        padding: 6,
        lineHeight: 1.1,
        boxShadow: data.hasSynthesis ? "0 0 0 3px rgba(14,165,233,0.25)" : undefined,
      }}
    >
      <span style={{ pointerEvents: "none" }}>{data.name}</span>
    </div>
  );
}

const NODE_TYPES = { entity: EntityNode };

function buildLayout(data: EntityGraphResponse): { nodes: Node[]; edges: Edge[] } {
  if (!data.nodes.length) return { nodes: [], edges: [] };

  // Simple circular layout — deterministic and readable for up to ~100 entities.
  // Scales radius with node count.
  const n = data.nodes.length;
  const radius = Math.max(160, Math.min(600, n * 14));
  const nodes: Node[] = data.nodes.map((e, i) => {
    const angle = (i / n) * 2 * Math.PI;
    const bg = TYPE_BG[e.entity_type] ?? TYPE_BG.other;
    const border = TYPE_BORDER[e.entity_type] ?? TYPE_BORDER.other;
    const size = Math.max(40, Math.min(120, 36 + Math.log2(e.item_count + 1) * 12));
    return {
      id: e.id,
      type: "entity",
      position: {
        x: radius * Math.cos(angle) + radius,
        y: radius * Math.sin(angle) + radius,
      },
      data: {
        name: e.name,
        size,
        bg,
        border,
        fontSize: Math.max(9, Math.min(13, 9 + Math.log2(e.item_count + 1))),
        hasSynthesis: e.has_synthesis,
      } satisfies EntityNodeData,
      style: { background: "transparent", border: "none", padding: 0, width: size, height: size },
    };
  });

  const edges: Edge[] = data.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    animated: false,
    style: {
      stroke: "#94a3b8",
      strokeWidth: Math.max(1, Math.min(4, e.weight)),
    },
    label: e.keywords ?? undefined,
    labelStyle: { fontSize: 9, fill: "#64748b" },
  }));

  return { nodes, edges };
}

export function EntityGraphCanvas({ data }: { data: EntityGraphResponse }) {
  const navigate = useNavigate();
  const layout = useMemo(() => buildLayout(data), [data]);
  const [nodes, setNodes, onNodesChange] = useNodesState(layout.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layout.edges);

  // Keep state in sync when the source data changes (e.g. type filter toggled).
  useEffect(() => {
    setNodes(layout.nodes);
    setEdges(layout.edges);
  }, [layout, setNodes, setEdges]);

  if (!data.nodes.length) {
    return (
      <div className="h-[60vh] flex items-center justify-center text-sm text-gray-500 dark:text-gray-400 border border-dashed border-gray-200 dark:border-gray-800 rounded-xl">
        No entities to display. Save some items and run enrichment to populate the graph.
      </div>
    );
  }

  return (
    <div className="h-[70vh] rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden bg-white dark:bg-gray-950">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={(_evt, n) => navigate(`/entities/${n.id}`)}
        fitView
        proOptions={{ hideAttribution: true }}
        minZoom={0.1}
        maxZoom={2}
      >
        <Background gap={24} color="#e2e8f0" />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable nodeColor="#0ea5e9" />
      </ReactFlow>
    </div>
  );
}
