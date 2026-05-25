import { useDroppable, useDndContext } from "@dnd-kit/core";
import { cn } from "../utils/cn";
import { Card } from "./Card";
import type { TaskSummary } from "../types";

export interface TreeNode {
  task: TaskSummary;
  children: TreeNode[];
  isOrphan: boolean;
}

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
  const task = node.task;
  const isExpanded = expanded.has(task.id);
  const hasChildren = node.children.length > 0;
  const isActive = task.state === "active";

  // Highlight card body when another card is dragged over it (reparent target).
  // The card's own sortable id is used; gap: and gap-end: ids are handled separately.
  const isReparentHovered =
    active !== null &&
    active.id !== task.id &&
    over?.id === task.id;

  return (
    <div>
      {/* Sibling-insert gap above this card */}
      <GapZone id={`gap:${task.id}`} depth={depth} />

      <div
        className="flex items-center gap-1"
        style={{ paddingLeft: `calc(${depth} * var(--tree-indent, 1.25rem))` }}
      >
        <button
          type="button"
          onClick={() => hasChildren && onToggle(task.id)}
          aria-label={isExpanded ? "Collapse" : "Expand"}
          aria-expanded={hasChildren ? isExpanded : undefined}
          className={[
            "flex h-5 w-5 shrink-0 items-center justify-center rounded text-ink-faint transition-transform duration-100",
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

        {/* Card body — drop zone for reparenting; the card's sortable id
            registers it as the droppable target when `over.id === task.id` */}
        <div
          className={cn(
            "min-w-0 flex-1 rounded-md transition-all duration-100",
            isReparentHovered && "ring-2 ring-inset ring-accent/60 bg-accent/5",
          )}
          title={isActive ? "Cannot move a running task" : undefined}
        >
          <Card
            task={task}
            onClick={() => onOpenTask?.(task.id)}
            density="tight"
            dragDisabled={isActive}
          />
        </div>
      </div>

      {isExpanded && hasChildren && (
        <div>
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
