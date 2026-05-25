import { useState, useMemo, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { SortableContext } from "@dnd-kit/sortable";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useReorderTasks } from "../hooks/useTasks";
import type { TaskState, TaskSummary } from "../types";
import { Card } from "./Card";
import { TreeNode as TreeNodeComponent, GapZone, type TreeNode } from "./TreeNode";

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

function extractDetail(msg: string): string {
  try {
    const idx = msg.indexOf("{");
    if (idx >= 0) {
      const obj = JSON.parse(msg.slice(idx)) as { detail?: string };
      if (obj.detail) return obj.detail;
    }
  } catch {
    // fall through
  }
  return msg;
}

// Disables the "cards shift aside" animation during drag — we use explicit
// drop zones instead of sortable reordering.
const noOpStrategy = () => null;

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

  const [activeTask, setActiveTask] = useState<TaskSummary | null>(null);
  const [errorToast, setErrorToast] = useState<string | null>(null);

  const qc = useQueryClient();
  const setParentMut = useMutation({
    mutationFn: ({ id, parentId }: { id: string; parentId: string | null }) =>
      api.setParent(id, parentId),
    onSuccess: () => {
      qc.invalidateQueries({
        predicate: (q) => Array.isArray(q.queryKey) && q.queryKey[0] === "board",
      });
    },
  });
  const reorderMut = useReorderTasks();

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } }),
  );

  function showToast(msg: string) {
    setErrorToast(msg);
    setTimeout(() => setErrorToast(null), 3000);
  }

  function doReorder(
    draggedId: string,
    lane: TaskState,
    insertBeforeId: string | null,
  ) {
    const sameLane = [...tasks]
      .filter((t) => t.state === lane)
      .sort((a, b) => a.manual_order - b.manual_order);
    const without = sameLane.filter((t) => t.id !== draggedId);
    const dragged = sameLane.find((t) => t.id === draggedId);
    if (!dragged) return Promise.resolve();

    let idx = insertBeforeId
      ? without.findIndex((t) => t.id === insertBeforeId)
      : without.length;
    if (idx === -1) idx = without.length;

    without.splice(idx, 0, dragged);
    return reorderMut.mutateAsync({
      lane,
      task_ids: without.map((t) => t.id),
    });
  }

  function onDragStart(e: DragStartEvent) {
    const found = tasks.find((t) => t.id === String(e.active.id));
    if (found) setActiveTask(found);
  }

  async function onDragEnd(e: DragEndEvent) {
    setActiveTask(null);
    if (!e.over) return;

    const draggedId = String(e.active.id);
    const overId = String(e.over.id);

    if (draggedId === overId) return;

    const dragged = tasks.find((t) => t.id === draggedId);
    if (!dragged || dragged.state === "active") return;

    if (overId.startsWith("gap:") || overId.startsWith("gap-end:")) {
      let insertBeforeId: string | null;
      let newParentId: string | null;

      if (overId.startsWith("gap:")) {
        const targetId = overId.slice(4);
        const target = tasks.find((t) => t.id === targetId);
        if (!target) return;
        newParentId = target.parent_id ?? null;
        insertBeforeId = targetId;
      } else {
        // "gap-end:root" or "gap-end:<parentId>"
        const parentPart = overId.slice(8);
        newParentId = parentPart === "root" ? null : parentPart;
        insertBeforeId = null;
      }

      const parentChanged = (dragged.parent_id ?? null) !== newParentId;

      try {
        if (parentChanged) {
          await setParentMut.mutateAsync({ id: draggedId, parentId: newParentId });
        }
        await doReorder(draggedId, dragged.state, insertBeforeId);
      } catch (err) {
        showToast(extractDetail((err as Error).message));
      }
    } else {
      // Drop on card body — reparent dragged under the target card
      const newParentId = overId;
      try {
        await setParentMut.mutateAsync({ id: draggedId, parentId: newParentId });
      } catch (err) {
        showToast(extractDetail((err as Error).message));
      }
    }
  }

  function onDragCancel() {
    setActiveTask(null);
  }

  if (roots.length === 0) {
    return <p className="py-8 text-center text-sm text-ink-faint">No tasks</p>;
  }

  return (
    <>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
        onDragCancel={onDragCancel}
      >
        <SortableContext items={allIds} strategy={noOpStrategy}>
          <div
            style={{ "--tree-indent": "1.25rem" } as React.CSSProperties}
            className="flex flex-col p-2"
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
            <GapZone id="gap-end:root" depth={0} />
          </div>
        </SortableContext>

        <DragOverlay dropAnimation={null}>
          {activeTask ? (
            <Card
              task={activeTask}
              onClick={() => {}}
              density="tight"
              isDragOverlay
            />
          ) : null}
        </DragOverlay>
      </DndContext>

      {errorToast && (
        <div
          role="alert"
          className="fixed bottom-4 right-4 z-50 rounded-md border border-danger bg-surface-1 px-3 py-2 text-sm text-danger shadow-lift"
        >
          {errorToast}
        </div>
      )}
    </>
  );
}
