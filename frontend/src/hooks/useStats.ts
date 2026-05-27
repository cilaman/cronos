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

export function useGlobalStats(params?: { from_dt?: string; to_dt?: string }) {
  return useQuery({
    queryKey: ["global-stats", params?.from_dt, params?.to_dt],
    queryFn: () => api.globalStats(params),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}
