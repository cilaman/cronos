import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { FeatureState } from "../types";

/**
 * Invalidates all three query keys required to keep every feature-related view in sync:
 * - ["features", spaceId]  — FeaturesBoard direct data
 * - ["board", spaceId]     — Tasks board shared Backlog column
 * - ["spaces"]             — sidebar space stats (feature counts)
 *
 * This helper MUST be called from every feature mutation's onSuccess handler.
 * Dropping any of the three keys silently desyncs the shared Backlog on the Tasks board (R4).
 */
export function invalidateFeatureQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  spaceId: string,
): void {
  queryClient.invalidateQueries({ queryKey: ["features", spaceId] });
  queryClient.invalidateQueries({ queryKey: ["board", spaceId] });
  queryClient.invalidateQueries({ queryKey: ["spaces"] });
}

/**
 * Fetches the FeatureBoard (5-lane kanban) for a given space.
 * Polls every 5 seconds to keep the shared Backlog column on the Tasks board
 * consistent with the Features board.
 */
export function useFeatureBoard(spaceId: string | null) {
  return useQuery({
    queryKey: ["features", spaceId],
    queryFn: () => api.features(spaceId!),
    enabled: spaceId !== null,
    refetchInterval: 5_000,
  });
}

/**
 * Mutation to transition a feature task to a new FeatureState.
 * On success, invalidates all three query keys (R4 triple-key contract).
 */
export function useTransitionFeatureState(spaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, state }: { taskId: string; state: FeatureState }) =>
      api.transitionFeatureState(taskId, state),
    onSuccess: () => {
      invalidateFeatureQueries(qc, spaceId);
    },
  });
}

/**
 * Mutation to create a new feature or fix task in a given space.
 * On success, invalidates all three query keys (R4 triple-key contract).
 */
export function useCreateFeature(spaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; type: "feature" | "fix"; description?: string }) =>
      api.createFeature(spaceId, body),
    onSuccess: () => {
      invalidateFeatureQueries(qc, spaceId);
    },
  });
}
