import { createContext, useContext } from "react";
import { useDroppable, useDndContext } from "@dnd-kit/core";
import { cn } from "../utils/cn";
import { STATE_BADGE } from "../state-badges";
import type { TaskSummary } from "../types";

export interface TreeNode {
  task: TaskSummary;
  children: TreeNode[];
  isOrphan: boolean;
}

// Context provides the tree container ref for keyboard navigation
export const TreeKbdCtx = createContext<React.RefObject<HTMLDivElement | null> | null>(null);

// Thin gap zone between tree nodes — drop here to reorder as sibling.
// The outer div is the full hit area; the inner line is the visual indicator.
export function GapZone({ id, depth }: { id: string; depth: number }) {
  const { isOver, setNodeRef } = useDroppable({ id });
  return (
    <div
      ref={setNodeRef}
      style={{
        paddingLeft: `calc(${depth} * var(--tree-indent, 1.25rem) + 1.5rem)`,
      }}
      className="flex h-4 items-center"
      aria-hidden="true"
    >
      <div
        className={cn(
          "h-0.5 w-full rounded-full transition-colors duration-100",
          isOver ? "bg-ink" : "bg-transparent",
        )}
      />
    </div>
  );
}

interface Props {
  node: TreeNode;
  depth: number;
  expanded: Set<string>;
  onToggle: (id: string) => void;
  onOpenTask?: (id: string) => void;
}

export function TreeNode({ node, depth, expanded, onToggle, onOpenTask }: Props) {
  const { active, over } = useDndContext();
  const containerRef = useContext(TreeKbdCtx);
  const task = node.task;
  const isExpanded = expanded.has(task.id);
  const hasChildren = node.children.length > 0;
  const isActive = task.state === "active";

  const isReparentHovered =
    active !== null &&
    active.id !== task.id &&
    over?.id === task.id;

  function handleKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (!containerRef?.current) return;
    const items = Array.from(
      containerRef.current.querySelectorAll<HTMLDivElement>('[role="treeitem"]'),
    );
    const idx = items.indexOf(e.currentTarget);

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        items[idx + 1]?.focus();
        break;
      case "ArrowUp":
        e.preventDefault();
        items[idx - 1]?.focus();
        break;
      case "ArrowLeft":
        e.preventDefault();
        if (hasChildren && isExpanded) {
          onToggle(task.id);
        } else if (task.parent_id) {
          const parentEl = containerRef.current.querySelector<HTMLElement>(
            `[data-task-id="${task.parent_id}"][role="treeitem"]`,
          );
          parentEl?.focus();
        }
        break;
      case "ArrowRight":
        e.preventDefault();
        if (hasChildren && !isExpanded) {
          onToggle(task.id);
        } else if (hasChildren && isExpanded) {
          // Focus first child — it is the next visible treeitem
          items[idx + 1]?.focus();
        }
        break;
      case "Enter":
        e.preventDefault();
        onOpenTask?.(task.id);
        break;
    }
  }

  return (
    <div>
      {/* Sibling-insert gap above this card */}
      <GapZone id={`gap:${task.id}`} depth={depth} />

      {/*
        role="treeitem" on the row div (not the outer wrapper) so that
        querySelectorAll('[role="treeitem"]') returns only the rows, not the
        children containers, preserving correct DOM-order navigation.
      */}
      <div
        role="treeitem"
        tabIndex={0}
        aria-expanded={hasChildren ? isExpanded : undefined}
        aria-level={depth + 1}
        data-task-id={task.id}
        onKeyDown={handleKeyDown}
        className="flex items-center gap-1 outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-accent/60"
        style={{ paddingLeft: `calc(${depth} * var(--tree-indent, 1.25rem))` }}
      >
        {/* Chevron: 40×40 tap target even though the icon is smaller */}
        <button
          type="button"
          tabIndex={-1}
          onClick={() => hasChildren && onToggle(task.id)}
          aria-label={isExpanded ? "Collapse" : "Expand"}
          aria-expanded={hasChildren ? isExpanded : undefined}
          className={[
            "flex h-10 w-10 shrink-0 items-center justify-center rounded text-ink-faint transition-transform duration-100",
            !hasChildren ? "invisible pointer-events-none" : "hover:text-ink",
            isExpanded ? "rotate-90" : "",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          {hasChildren && (
            <svg
              width="8"
              height="8"
              viewBox="0 0 8 8"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M2 1.5l3.5 2.5L2 6.5" />
            </svg>
          )}
        </button>

        {node.isOrphan && (
          <span
            className="h-2 w-2 shrink-0 rounded-full bg-ink-faint/50 cursor-help"
            title="Orphan — parent task is missing or archived"
            aria-label="orphan"
          />
        )}

        {/* Compact row — drop zone for reparenting */}
        <div
          className={cn(
            "min-w-0 flex-1 rounded-md transition-all duration-100",
            isReparentHovered && "ring-2 ring-inset ring-accent/60 bg-accent/5",
          )}
          title={isActive ? "Cannot move a running task" : undefined}
        >
          <button
            type="button"
            onClick={() => onOpenTask?.(task.id)}
            className="relative flex min-h-[36px] w-full items-center gap-2 rounded-md border border-hairline bg-surface-2 px-2.5 py-1.5 text-left shadow-inset-hairline transition hover:border-hairline-strong hover:bg-surface-3 focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
          >
            {isActive && (
              <span
                className="absolute right-2 top-1/2 -translate-y-1/2 h-1.5 w-1.5 rounded-full bg-accent-bright anim-pulse-dot"
                aria-label="Running"
              />
            )}
            <span
              className={cn(
                "shrink-0 rounded px-1 py-px font-mono text-[9px] font-semibold uppercase tracking-wide",
                STATE_BADGE[task.state],
              )}
            >
              {task.state}
            </span>
            <h3 className="min-w-0 truncate text-sm font-semibold leading-snug text-ink">
              {task.title}
            </h3>
          </button>
        </div>
      </div>

      {isExpanded && hasChildren && (
        <div
          role="group"
          className="relative border-l border-hairline"
          style={{
            marginLeft: `calc(${depth} * var(--tree-indent, 1.25rem) + 1.5rem)`,
          }}
        >
          {node.children.map((child) => (
            <TreeNode
              key={child.task.id}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              onToggle={onToggle}
              onOpenTask={onOpenTask}
            />
          ))}
          {/* Terminal gap: drop here to append as last child of this node */}
          <GapZone id={`gap-end:${task.id}`} depth={depth + 1} />
        </div>
      )}
    </div>
  );
}
