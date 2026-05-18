import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function useTestReports(spaceId: string | undefined) {
  return useQuery({
    queryKey: ["test-reports", spaceId],
    queryFn: () => api.testReports(spaceId!),
    enabled: !!spaceId,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useLatestTestReport(spaceId: string | undefined) {
  return useQuery({
    queryKey: ["test-report-latest", spaceId],
    queryFn: () => api.testReportLatest(spaceId!),
    enabled: !!spaceId,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useTestReport(spaceId: string | undefined, reportId: string | undefined) {
  return useQuery({
    queryKey: ["test-report", spaceId, reportId],
    queryFn: () => api.testReport(spaceId!, reportId!),
    enabled: !!spaceId && !!reportId,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useTaskTestReports(taskId: string | undefined) {
  return useQuery({
    queryKey: ["task-test-reports", taskId],
    queryFn: () => api.taskTestReports(taskId!),
    enabled: !!taskId,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useTaskTestReportLatest(taskId: string | undefined) {
  return useQuery({
    queryKey: ["task-test-report-latest", taskId],
    queryFn: () => api.taskTestReportLatest(taskId!),
    enabled: !!taskId,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}
