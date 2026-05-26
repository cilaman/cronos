import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";

export function useMemoryItems(scope: string) {
  return useQuery({
    queryKey: ["memory", scope],
    queryFn: () => api.memoryList(scope),
    staleTime: 30_000,
  });
}

export function useConfirmMemory(scope: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (itemId: string) => api.memoryConfirm(scope, itemId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["memory", scope] }),
  });
}

export function useRejectMemory(scope: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (itemId: string) => api.memoryReject(scope, itemId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["memory", scope] }),
  });
}
