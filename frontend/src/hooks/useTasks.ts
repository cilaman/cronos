import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { AgentMode, AgentModel, TaskState } from "../types";

export function useBoard(spaceId: string | null = null) {
  return useQuery({
    queryKey: ["board", spaceId ?? "all"],
    queryFn: () => api.board(spaceId),
    refetchInterval: 5_000,
  });
}

export function useTask(id: string | null) {
  return useQuery({
    queryKey: ["task", id],
    queryFn: () => api.task(id!),
    enabled: id !== null,
  });
}

function invalidateBoards(qc: ReturnType<typeof useQueryClient>) {
  // Predicate-match so every cached board variant (per space + "all") refreshes.
  qc.invalidateQueries({
    predicate: (q) => Array.isArray(q.queryKey) && q.queryKey[0] === "board",
  });
}

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.create,
    onSuccess: () => {
      invalidateBoards(qc);
      qc.invalidateQueries({ queryKey: ["spaces"] });
      qc.invalidateQueries({ queryKey: ["activity"] });
    },
  });
}

export function useUpdateTask(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      title?: string;
      brief?: string;
      agent_mode?: AgentMode;
      agent_model?: AgentModel;
    }) => api.update(id, body),
    onSuccess: () => {
      invalidateBoards(qc);
      qc.invalidateQueries({ queryKey: ["task", id] });
    },
  });
}

export function useReplyToTask(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (message: string) => api.reply(id, message),
    onSuccess: (updatedTask) => {
      qc.setQueryData(["task", id], updatedTask);
      invalidateBoards(qc);
      qc.invalidateQueries({ queryKey: ["task", id] });
    },
  });
}

export function useStopTask(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.stop(id),
    onSuccess: () => {
      invalidateBoards(qc);
      qc.invalidateQueries({ queryKey: ["task", id] });
    },
  });
}

export function useStartTask(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.start(id),
    onSuccess: () => {
      invalidateBoards(qc);
      qc.invalidateQueries({ queryKey: ["task", id] });
      qc.invalidateQueries({ queryKey: ["activity"] });
    },
  });
}

export function useDeleteTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(id),
    onSuccess: () => {
      invalidateBoards(qc);
      qc.invalidateQueries({ queryKey: ["spaces"] });
    },
  });
}

export function useTransitionTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, state }: { id: string; state: TaskState }) =>
      api.transition(id, state),
    onSettled: () => invalidateBoards(qc),
  });
}

export function useArchiveTask(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.transition(id, "archived"),
    onSuccess: () => {
      invalidateBoards(qc);
      qc.invalidateQueries({ queryKey: ["task", id] });
      qc.invalidateQueries({ queryKey: ["spaces"] });
      qc.invalidateQueries({ queryKey: ["archived"] });
    },
  });
}

export function useArchivedTasks(spaceId: string | null = null) {
  return useQuery({
    queryKey: ["archived", spaceId ?? "all"],
    queryFn: () => api.archived(spaceId),
    refetchInterval: 10_000,
  });
}

export function useUnarchiveTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.transition(id, "backlog"),
    onSuccess: (_data, id) => {
      invalidateBoards(qc);
      qc.invalidateQueries({ queryKey: ["task", id] });
      qc.invalidateQueries({ queryKey: ["spaces"] });
      qc.invalidateQueries({ queryKey: ["archived"] });
    },
  });
}
