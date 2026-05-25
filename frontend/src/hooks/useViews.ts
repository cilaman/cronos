import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";

export function useViews(spaceId: string | null) {
  return useQuery({
    queryKey: ["views", spaceId],
    queryFn: () => api.spaceViews(spaceId!),
    enabled: spaceId !== null,
    staleTime: 30_000,
  });
}

function invalidateViewsAndBoard(qc: ReturnType<typeof useQueryClient>, spaceId: string) {
  qc.invalidateQueries({ queryKey: ["views", spaceId] });
  qc.invalidateQueries({ queryKey: ["board"] });
}

export function useCreateView(spaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; lanes: string[]; type_filter?: string[] | null; default?: boolean }) =>
      api.createView(spaceId, body),
    onSuccess: () => invalidateViewsAndBoard(qc, spaceId),
  });
}

export function useUpdateView(spaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      viewId,
      ...body
    }: { viewId: string; name?: string; lanes?: string[]; type_filter?: string[] | null; default?: boolean }) =>
      api.updateView(spaceId, viewId, body),
    onSuccess: () => invalidateViewsAndBoard(qc, spaceId),
  });
}

export function useDeleteView(spaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (viewId: string) => api.deleteView(spaceId, viewId),
    onSuccess: () => invalidateViewsAndBoard(qc, spaceId),
  });
}
