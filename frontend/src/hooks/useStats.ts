import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

type TimeFrame = { from?: string; to?: string };

export function useTaskStats(taskId: string | undefined, timeFrame?: TimeFrame) {
  return useQuery({
    queryKey: ["task-stats", taskId, timeFrame],
    queryFn: () => api.taskStats(taskId!, timeFrame),
    enabled: !!taskId,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}

export function useSpaceStats(spaceId: string | undefined, timeFrame?: TimeFrame) {
  return useQuery({
    queryKey: ["space-stats", spaceId, timeFrame],
    queryFn: () => api.spaceStats(spaceId!, timeFrame),
    enabled: !!spaceId,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}

export function useGlobalStats(timeFrame?: TimeFrame) {
  return useQuery({
    queryKey: ["global-stats", timeFrame],
    queryFn: () => api.globalStats(timeFrame),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}
