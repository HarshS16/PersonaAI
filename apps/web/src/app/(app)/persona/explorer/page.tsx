"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  Position,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ArrowLeft } from "lucide-react";
import { dashboardApi, type GraphNode } from "@/lib/dashboard";
import { Skeleton } from "@/components/ui/skeleton";

const COLORS: Record<string, string> = {
  persona: "#6366f1",
  skill: "#0ea5e9",
  project: "#10b981",
  experience: "#f59e0b",
  education: "#a855f7",
};

/** Lay nodes out in concentric columns by type around the persona root. */
function layout(nodes: GraphNode[]): Node[] {
  const groups: Record<string, GraphNode[]> = {};
  for (const n of nodes) {
    if (n.type === "persona") continue;
    (groups[n.type] ??= []).push(n);
  }
  const columns = ["skill", "project", "experience", "education"];
  const out: Node[] = [];

  const persona = nodes.find((n) => n.type === "persona");
  if (persona) {
    out.push({
      id: persona.id,
      position: { x: 0, y: 0 },
      data: { label: persona.label },
      style: nodeStyle("persona", true),
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    });
  }

  columns.forEach((type, col) => {
    const items = groups[type] ?? [];
    const x = (col + 1) * 260;
    items.forEach((n, i) => {
      out.push({
        id: n.id,
        position: { x, y: (i - (items.length - 1) / 2) * 70 },
        data: { label: n.label },
        style: nodeStyle(type, false),
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      });
    });
  });
  return out;
}

function nodeStyle(type: string, root: boolean): React.CSSProperties {
  const color = COLORS[type] ?? "#64748b";
  return {
    background: root ? color : `${color}22`,
    color: root ? "white" : "inherit",
    border: `1px solid ${color}`,
    borderRadius: 8,
    padding: "6px 10px",
    fontSize: 12,
    fontWeight: root ? 600 : 500,
    width: 170,
    textAlign: "center" as const,
  };
}

export default function ExplorerPage() {
  const { data, isLoading } = useQuery({ queryKey: ["persona", "graph"], queryFn: dashboardApi.graph });

  const nodes = useMemo<Node[]>(() => (data ? layout(data.nodes) : []), [data]);
  const edges = useMemo<Edge[]>(
    () =>
      data
        ? data.edges.map((e) => ({
            id: e.id,
            source: e.source,
            target: e.target,
            label: e.label,
            labelStyle: { fontSize: 9, fill: "#94a3b8" },
            style: { stroke: "#cbd5e1" },
            markerEnd: { type: MarkerType.ArrowClosed, color: "#cbd5e1" },
          }))
        : [],
    [data],
  );

  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-5xl flex-col">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Persona Explorer</h2>
          <p className="text-sm text-muted-foreground">
            Skills, projects, experience and how they connect
            {data ? ` · ${data.evidence_total} evidence items` : ""}.
          </p>
        </div>
        <Link
          href="/persona"
          className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-muted"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Persona
        </Link>
      </div>

      <div className="flex-1 overflow-hidden rounded-lg border">
        {isLoading || !data ? (
          <Skeleton className="h-full w-full" />
        ) : data.nodes.length <= 1 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            Add skills, projects or experience to see your persona graph.
          </div>
        ) : (
          <ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }}>
            <Background />
            <Controls />
          </ReactFlow>
        )}
      </div>
    </div>
  );
}
