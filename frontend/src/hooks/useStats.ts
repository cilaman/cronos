import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function useTaskStats(taskId: string | undefined) {
  return useQuery({
    queryKey: ["task-stats", taskId],
    queryFn: () => api.taskStats(taskId!),
    enabled: !!taskId,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}

export function useSpaceStats(spaceId: string | undefined) {
  return useQuery({
    queryKey: ["space-stats", spaceId],
    queryFn: () => api.spaceStats(spaceId!),
    enabled: !!spaceId,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}

export function useGlobalStats() {
  return useQuery({
    queryKey: ["global-stats"],
    queryFn: () => api.globalStats(),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}
