import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import type { Harness } from '../types';

// 1. useHarnesses — list all harnesses in a space
export function useHarnesses(spaceId: string) {
  return useQuery({
    queryKey: ['harnesses', spaceId],
    queryFn: () => api.listHarnesses(spaceId),
    enabled: !!spaceId,
  });
}

// 2. useHarness — get a single harness by name
export function useHarness(spaceId: string, name: string) {
  return useQuery({
    queryKey: ['harness', spaceId, name],
    queryFn: () => api.getHarness(spaceId, name),
    enabled: !!spaceId && !!name,
    refetchOnWindowFocus: false,
  });
}

// 3. useSaveHarness — GET-then-PUT mutation that preserves created_at
export function useSaveHarness(spaceId: string, name: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (canvasState: Partial<Harness>) => {
      // GET first to preserve created_at and server-side fields
      const existing = await api.getHarness(spaceId, name);
      // Merge canvas state into existing, preserving created_at
      const merged: Harness = { ...existing, ...canvasState, created_at: existing.created_at };
      return api.updateHarness(spaceId, name, merged);
    },
    onSuccess: () => {
      // Invalidate BOTH query keys
      queryClient.invalidateQueries({ queryKey: ['harnesses', spaceId] });
      queryClient.invalidateQueries({ queryKey: ['harness', spaceId, name] });
    },
  });
}

// 4. useCreateHarness — create a new empty harness
export function useCreateHarness(spaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; description?: string }) =>
      api.createHarness(spaceId, {
        name: payload.name,
        description: payload.description,
        nodes: [],
        edges: [],
        variables: {},
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['harnesses', spaceId] });
    },
  });
}

// 5. useDeleteHarness — delete a harness by name
export function useDeleteHarness(spaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.deleteHarness(spaceId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['harnesses', spaceId] });
    },
  });
}
