import { useMemo, useState } from "react";
import * as dagre from "@dagrejs/dagre";
import type { Task, TaskSummary } from "../types";
import { STATE_BADGE } from "../state-badges";

const NODE_W = 180;
const NODE_H = 56;
const SVG_PAD = 16;

const STATE_DOT: Record<string, string> = {
  backlog: "bg-surface-3",
  active: "bg-emerald-400",
  waiting: "bg-amber-400",
  done: "bg-sky-400",
  archived: "bg-surface-3",
};

interface LayoutNode extends TaskSummary {
  x: number;
  y: number;
}

interface LayoutEdge {
  points: Array<{ x: number; y: number }>;
  sourceState: string;
}

export interface Props {
  goal: Task;
  children: TaskSummary[];
  onOpenTask: (id: string) => void;
  runningIds: Set<string>;
}

function edgeCssColor(state: string): string {
  if (state === "waiting") return "rgb(var(--color-warning))";
  if (state === "done") return "rgb(var(--color-ink))";
  return "rgb(var(--color-ink-faint))";
}

function edgeMarkerKey(state: string): "faint" | "amber" | "ink" {
  if (state === "waiting") return "amber";
  if (state === "done") return "ink";
  return "faint";
}

function pathFromPoints(pts: Array<{ x: number; y: number }>, pad: number): string {
  const p = pts.map((pt) => ({ x: pt.x + pad, y: pt.y + pad }));
  if (p.length < 2) return "";
  if (p.length === 2) {
    const cy = (p[0].y + p[1].y) / 2;
    return `M ${p[0].x} ${p[0].y} C ${p[0].x} ${cy}, ${p[1].x} ${cy}, ${p[1].x} ${p[1].y}`;
  }
  const segments = p.slice(1).map((pt) => `L ${pt.x} ${pt.y}`);
  return [`M ${p[0].x} ${p[0].y}`, ...segments].join(" ");
}

function FlatList({
  tasks,
  onOpenTask,
}: {
  tasks: TaskSummary[];
  onOpenTask: (id: string) => void;
}) {
  if (tasks.length === 0) return null;
  return (
    <div className="space-y-1">
      {tasks.map((child) => (
        <button
          key={child.id}
          type="button"
          onClick={() => onOpenTask(child.id)}
          className="flex w-full items-center gap-2 rounded border border-hairline px-2.5 py-1.5 text-left transition hover:border-hairline-strong hover:bg-surface-2"
        >
          <span
            className={`rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.18em] ${STATE_BADGE[child.state] ?? STATE_BADGE.backlog}`}
          >
            {child.state}
          </span>
          <span className="truncate text-xs text-ink">{child.title}</span>
        </button>
      ))}
    </div>
  );
}

function useGraphLayout(children: TaskSummary[]) {
  const childIds = useMemo(() => new Set(children.map((c) => c.id)), [children]);

  return useMemo(() => {
    if (children.length === 0) {
      return { layoutNodes: [], layoutEdges: [], svgWidth: 0, svgHeight: 0 };
    }

    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({ rankdir: "TB", nodesep: 24, ranksep: 32 });

    for (const child of children) {
      g.setNode(child.id, { width: NODE_W, height: NODE_H });
    }
    for (const child of children) {
      for (const depId of child.depends_on ?? []) {
        if (childIds.has(depId)) {
          g.setEdge(depId, child.id);
        }
      }
    }

    dagre.layout(g);

    const layoutNodes: LayoutNode[] = children.map((child) => {
      const pos = g.node(child.id);
      return { ...child, x: pos.x, y: pos.y };
    });

    const layoutEdges: LayoutEdge[] = g.edges().map((e) => {
      const edge = g.edge(e);
      const src = children.find((c) => c.id === e.v);
      return {
        points: (edge.points ?? []) as Array<{ x: number; y: number }>,
        sourceState: src?.state ?? "backlog",
      };
    });

    const info = g.graph();
    return {
      layoutNodes,
      layoutEdges,
      svgWidth: (info.width ?? NODE_W) + SVG_PAD * 2,
      svgHeight: (info.height ?? NODE_H) + SVG_PAD * 2,
    };
  }, [children, childIds]);
}

const MARKER_COLORS: Record<"faint" | "amber" | "ink", string> = {
  faint: "rgb(var(--color-ink-faint))",
  amber: "rgb(var(--color-warning))",
  ink: "rgb(var(--color-ink))",
};

function DagSvg({
  layoutNodes,
  layoutEdges,
  svgWidth,
  svgHeight,
  onOpenTask,
  runningIds,
}: {
  layoutNodes: LayoutNode[];
  layoutEdges: LayoutEdge[];
  svgWidth: number;
  svgHeight: number;
  onOpenTask: (id: string) => void;
  runningIds: Set<string>;
}) {
  return (
    <svg
      width={svgWidth}
      height={svgHeight}
      style={{ display: "block", minWidth: svgWidth }}
      aria-label="Dependency graph"
    >
      <defs>
        {(["faint", "amber", "ink"] as const).map((key) => (
          <marker
            key={key}
            id={`dag-arrow-${key}`}
            markerWidth="8"
            markerHeight="8"
            refX="6"
            refY="3"
            orient="auto"
          >
            <path
              d="M 0 0 L 0 6 L 8 3 z"
              style={{ fill: MARKER_COLORS[key] }}
            />
          </marker>
        ))}
      </defs>

      {layoutEdges.map((edge, i) => {
        const d = pathFromPoints(edge.points, SVG_PAD);
        if (!d) return null;
        const mKey = edgeMarkerKey(edge.sourceState);
        return (
          <path
            key={i}
            d={d}
            fill="none"
            strokeWidth={1.5}
            style={{ stroke: edgeCssColor(edge.sourceState) }}
            markerEnd={`url(#dag-arrow-${mKey})`}
          />
        );
      })}

      {layoutNodes.map((node) => {
        const x = node.x - NODE_W / 2 + SVG_PAD;
        const y = node.y - NODE_H / 2 + SVG_PAD;
        const isRunning = runningIds.has(node.id);
        const isWaiting = node.state === "waiting";
        const isDone = node.state === "done";

        return (
          <foreignObject
            key={node.id}
            x={x}
            y={y}
            width={NODE_W}
            height={NODE_H}
          >
            <button
              type="button"
              onClick={() => onOpenTask(node.id)}
              data-testid={`dag-node-${node.id}`}
              className={[
                "h-full w-full cursor-pointer rounded border bg-surface-1 px-2.5 py-1.5 text-left transition",
                isWaiting
                  ? "border-amber-300 dark:border-amber-400/40"
                  : "border-hairline hover:border-hairline-strong hover:bg-surface-2",
                isDone ? "opacity-60" : "",
                isRunning ? "ring-2 ring-accent animate-pulse" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <div className="flex items-center gap-1.5 overflow-hidden">
                <span
                  className={`h-2 w-2 flex-shrink-0 rounded-full ${STATE_DOT[node.state] ?? "bg-surface-3"}`}
                />
                <span className="flex-1 truncate text-[11px] font-medium leading-none text-ink">
                  {node.title}
                </span>
                <span className="flex-shrink-0 font-mono text-[9px] text-ink-faint">
                  P{node.priority}
                </span>
              </div>
              <div className="mt-1.5">
                <span
                  className={`rounded px-1 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] ${STATE_BADGE[node.state] ?? STATE_BADGE.backlog}`}
                >
                  {node.state}
                </span>
              </div>
            </button>
          </foreignObject>
        );
      })}
    </svg>
  );
}

export function GoalDependencyGraph({
  goal: _goal,
  children,
  onOpenTask,
  runningIds,
}: Props) {
  const [viewMode, setViewMode] = useState<"graph" | "list">("graph");
  const { layoutNodes, layoutEdges, svgWidth, svgHeight } =
    useGraphLayout(children);

  if (children.length === 0) {
    return (
      <div className="rounded border border-dashed border-hairline px-4 py-5 text-center">
        <p className="text-xs text-ink-faint">No children yet</p>
      </div>
    );
  }

  return (
    <div>
      {/* Mobile: always flat list */}
      <div className="sm:hidden">
        <FlatList tasks={children} onOpenTask={onOpenTask} />
      </div>

      {/* Desktop: graph/list toggle */}
      <div className="hidden sm:block">
        <div className="mb-2 flex justify-end">
          <div className="inline-flex rounded border border-hairline text-[10px]">
            <button
              type="button"
              onClick={() => setViewMode("graph")}
              className={`px-2 py-0.5 transition ${viewMode === "graph" ? "bg-surface-2 text-ink" : "text-ink-faint hover:text-ink"}`}
            >
              Graph
            </button>
            <button
              type="button"
              onClick={() => setViewMode("list")}
              className={`border-l border-hairline px-2 py-0.5 transition ${viewMode === "list" ? "bg-surface-2 text-ink" : "text-ink-faint hover:text-ink"}`}
            >
              List view
            </button>
          </div>
        </div>

        {viewMode === "graph" ? (
          <div className="overflow-x-auto rounded border border-hairline bg-surface-1 p-2">
            <DagSvg
              layoutNodes={layoutNodes}
              layoutEdges={layoutEdges}
              svgWidth={svgWidth}
              svgHeight={svgHeight}
              onOpenTask={onOpenTask}
              runningIds={runningIds}
            />
          </div>
        ) : (
          <FlatList tasks={children} onOpenTask={onOpenTask} />
        )}
      </div>
    </div>
  );
}
