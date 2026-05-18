import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function useTaskTraces(taskId: string | undefined) {
  return useQuery({
    queryKey: ["task-traces", taskId],
    queryFn: () => api.taskTraces(taskId!),
    enabled: !!taskId,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}

export function useTaskTrace(taskId: string | undefined, runIndex: number) {
  return useQuery({
    queryKey: ["task-trace", taskId, runIndex],
    queryFn: () => api.taskTrace(taskId!, runIndex),
    enabled: !!taskId,
    staleTime: 60_000,
  });
}
