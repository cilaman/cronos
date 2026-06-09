import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { FeatureRead, FeatureState } from "../types";

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
    mutationFn: (body: { title: string; type: "feature" | "fix"; description?: string; priority?: number }) =>
      api.createFeature(spaceId, body),
    onSuccess: () => {
      invalidateFeatureQueries(qc, spaceId);
    },
  });
}

/**
 * Fetches a single feature/fix by ID.
 * Mirrors useTask() — enabled only when featureId is non-null.
 */
export function useFeature(featureId: string | null) {
  return useQuery<FeatureRead>({
    queryKey: ["feature", featureId],
    queryFn: () => api.getFeature(featureId!),
    enabled: featureId !== null,
  });
}

/**
 * Mutation to edit a feature's title and/or brief.
 * Invalidates ["feature", featureId] for immediate refetch plus the R4 triple-key.
 */
export function usePatchFeature() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      featureId,
      body,
    }: {
      featureId: string;
      body: { title?: string; brief?: string; type?: "feature" | "fix" };
    }) => api.patchFeature(featureId, body),
    onSuccess: (result: FeatureRead) => {
      qc.invalidateQueries({ queryKey: ["feature", result.id] });
      invalidateFeatureQueries(qc, result.space_id);
    },
  });
}

/**
 * Mutation to trigger decomposition of a feature (POST /process).
 * Transitions feature to PROCESSING and enqueues the S4 decomposition agent.
 * Invalidates ["feature", featureId] and the R4 triple-key.
 */
export function useProcessFeature() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (featureId: string) => api.processFeature(featureId),
    onSuccess: (result: FeatureRead) => {
      qc.invalidateQueries({ queryKey: ["feature", result.id] });
      invalidateFeatureQueries(qc, result.space_id);
    },
  });
}

/**
 * Mutation to link or unlink a task to a feature via PATCH /realize.
 * Set body.feature_id to null to unlink.
 * Invalidates ["feature", featureId] and the R4 triple-key.
 */
export function useSetRealize() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      featureId,
      body,
    }: {
      featureId: string;
      body: { item_id: string; feature_id: string | null };
    }) => api.setRealize(featureId, body),
    onSuccess: (result: FeatureRead) => {
      qc.invalidateQueries({ queryKey: ["feature", result.id] });
      invalidateFeatureQueries(qc, result.space_id);
    },
  });
}
