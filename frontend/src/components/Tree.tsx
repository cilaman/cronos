import { useState, useMemo, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { DndContext } from "@dnd-kit/core";
import { SortableContext } from "@dnd-kit/sortable";
import type { TaskSummary } from "../types";
import { TreeNode as TreeNodeComponent, type TreeNode } from "./TreeNode";

export { type TreeNode };

export function buildTree(tasks: TaskSummary[]): TreeNode[] {
  const taskSet = new Set(tasks.map((t) => t.id));

  const nodeMap = new Map<string, TreeNode>();
  for (const task of tasks) {
    nodeMap.set(task.id, {
      task,
      children: [],
      isOrphan: !!(task.parent_id && !taskSet.has(task.parent_id)),
    });
  }

  const roots: TreeNode[] = [];
  for (const node of nodeMap.values()) {
    const parentId = node.task.parent_id;
    if (parentId && nodeMap.has(parentId)) {
      nodeMap.get(parentId)!.children.push(node);
    } else {
      roots.push(node);
    }
  }

  const compareFn = (a: TreeNode, b: TreeNode): number => {
    if (a.task.manual_order !== b.task.manual_order)
      return a.task.manual_order - b.task.manual_order;
    if (a.task.priority !== b.task.priority)
      return b.task.priority - a.task.priority; // DESC
    if (a.task.created_at < b.task.created_at) return -1;
    if (a.task.created_at > b.task.created_at) return 1;
    return 0;
  };

  function sortRecursive(nodes: TreeNode[]): TreeNode[] {
    nodes.sort(compareFn);
    for (const node of nodes) {
      node.children = sortRecursive(node.children);
    }
    return nodes;
  }

  return sortRecursive(roots);
}

function getAncestorIds(roots: TreeNode[], targetId: string): Set<string> {
  const result = new Set<string>();

  function search(nodes: TreeNode[], ancestors: string[]): boolean {
    for (const node of nodes) {
      if (node.task.id === targetId) {
        for (const id of ancestors) result.add(id);
        return true;
      }
      if (search(node.children, [...ancestors, node.task.id])) return true;
    }
    return false;
  }

  search(roots, []);
  return result;
}

function flattenIds(nodes: TreeNode[]): string[] {
  const ids: string[] = [];
  function collect(list: TreeNode[]) {
    for (const node of list) {
      ids.push(node.task.id);
      collect(node.children);
    }
  }
  collect(nodes);
  return ids;
}

interface Props {
  tasks: TaskSummary[];
  spaceId?: string;
  onOpenTask?: (id: string) => void;
}

export function Tree({ tasks, onOpenTask }: Props) {
  const [searchParams] = useSearchParams();
  const openId = searchParams.get("task");

  const roots = useMemo(() => buildTree(tasks), [tasks]);

  const [expanded, setExpanded] = useState<Set<string>>(() =>
    openId ? getAncestorIds(roots, openId) : new Set<string>()
  );

  const prevOpenIdRef = useRef<string | null>(openId);

  useEffect(() => {
    if (openId && openId !== prevOpenIdRef.current) {
      const ancestors = getAncestorIds(roots, openId);
      if (ancestors.size > 0) {
        setExpanded((prev) => {
          const next = new Set(prev);
          for (const id of ancestors) next.add(id);
          return next;
        });
      }
    }
    prevOpenIdRef.current = openId;
  }, [openId, roots]);

  const handleToggle = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const allIds = useMemo(() => flattenIds(roots), [roots]);

  if (roots.length === 0) {
    return <p className="py-8 text-center text-sm text-ink-faint">No tasks</p>;
  }

  return (
    <DndContext>
      <SortableContext items={allIds}>
        <div
          style={{ "--tree-indent": "1.25rem" } as React.CSSProperties}
          className="flex flex-col gap-1 p-2"
        >
          {roots.map((node) => (
            <TreeNodeComponent
              key={node.task.id}
              node={node}
              depth={0}
              expanded={expanded}
              onToggle={handleToggle}
              onOpenTask={onOpenTask}
            />
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
}
