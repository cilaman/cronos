import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { Board, TaskState } from "../types";

export function useBoard() {
  return useQuery({
    queryKey: ["board"],
    queryFn: api.board,
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

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["board"] }),
  });
}

export function useUpdateTask(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title?: string; brief?: string }) => api.update(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["board"] });
      qc.invalidateQueries({ queryKey: ["task", id] });
    },
  });
}

export function useReplyToTask(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (message: string) => api.reply(id, message),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["board"] });
      qc.invalidateQueries({ queryKey: ["task", id] });
    },
  });
}

export function useStartTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.start(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["board"] });
      qc.invalidateQueries({ queryKey: ["task", id] });
    },
  });
}

export function useDeleteTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["board"] }),
  });
}

export function useTransitionTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, state }: { id: string; state: TaskState }) =>
      api.transition(id, state),
    onMutate: async ({ id, state }) => {
      await qc.cancelQueries({ queryKey: ["board"] });
      const previous = qc.getQueryData<Board>(["board"]);
      if (previous) {
        const next: Board = {
          backlog: [...previous.backlog],
          active: [...previous.active],
          waiting: [...previous.waiting],
          done: [...previous.done],
        };
        for (const lane of ["backlog", "active", "waiting", "done"] as const) {
          const idx = next[lane].findIndex((t) => t.id === id);
          if (idx >= 0) {
            const [task] = next[lane].splice(idx, 1);
            next[state] = [{ ...task, state }, ...next[state]];
            break;
          }
        }
        qc.setQueryData<Board>(["board"], next);
      }
      return { previous };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(["board"], ctx.previous);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["board"] }),
  });
}
