import { Card } from "./Card";
import type { TaskSummary } from "../types";

export interface TreeNode {
  task: TaskSummary;
  children: TreeNode[];
  isOrphan: boolean;
}

interface Props {
  node: TreeNode;
  depth: number;
  expanded: Set<string>;
  onToggle: (id: string) => void;
  onOpenTask?: (id: string) => void;
}

export function TreeNode({ node, depth, expanded, onToggle, onOpenTask }: Props) {
  const isExpanded = expanded.has(node.task.id);
  const hasChildren = node.children.length > 0;

  return (
    <div>
      <div
        className="flex items-center gap-1"
        style={{ paddingLeft: `calc(${depth} * var(--tree-indent, 1.25rem))` }}
      >
        <button
          type="button"
          onClick={() => hasChildren && onToggle(node.task.id)}
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

        <div className="min-w-0 flex-1">
          <Card
            task={node.task}
            onClick={() => onOpenTask?.(node.task.id)}
            density="tight"
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
        </div>
      )}
    </div>
  );
}
