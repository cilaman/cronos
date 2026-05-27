import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { type TimeFrame, timeFrameToDateParams } from "../components/TimeFrameSelector";

export function useTaskStats(taskId: string | undefined) {
  return useQuery({
    queryKey: ["task-stats", taskId],
    queryFn: () => api.taskStats(taskId!),
    enabled: !!taskId,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}

function timeFrameKey(tf: TimeFrame | undefined): string[] {
  if (!tf) return ["all"];
  if (tf.preset === "custom") return ["custom", tf.from, tf.to];
  return [tf.preset];
}

export function useSpaceStats(spaceId: string | undefined, timeFrame?: TimeFrame) {
  return useQuery({
    queryKey: ["space-stats", spaceId, ...timeFrameKey(timeFrame)],
    queryFn: () => {
      const { fromDt, toDt } = timeFrame ? timeFrameToDateParams(timeFrame) : {};
      return api.spaceStats(spaceId!, fromDt, toDt);
    },
    enabled: !!spaceId,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}

export function useGlobalStats(timeFrame?: TimeFrame) {
  return useQuery({
    queryKey: ["global-stats", ...timeFrameKey(timeFrame)],
    queryFn: () => {
      const { fromDt, toDt } = timeFrame ? timeFrameToDateParams(timeFrame) : {};
      return api.globalStats(fromDt, toDt);
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}
