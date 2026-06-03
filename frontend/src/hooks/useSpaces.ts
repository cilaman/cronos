import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";

export function useSpaces() {
  return useQuery({
    queryKey: ["spaces"],
    queryFn: api.spaces,
    refetchInterval: 10_000,
  });
}

export function useSpace(id: string | null) {
  return useQuery({
    queryKey: ["space", id],
    queryFn: () => api.space(id!),
    enabled: id !== null,
  });
}

export function useActivity(limit = 50, spaceId: string | null = null) {
  return useQuery({
    queryKey: ["activity", spaceId ?? "all", limit],
    queryFn: () => api.activity(limit, spaceId),
    refetchInterval: 15_000,
  });
}

function invalidateBoards(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({
    predicate: (q) => Array.isArray(q.queryKey) && q.queryKey[0] === "board",
  });
}

export function useCreateSpace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createSpace,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["spaces"] });
      qc.invalidateQueries({ queryKey: ["activity"] });
    },
  });
}

export function useUpdateSpace(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      name?: string;
      color?: string;
      icon?: string | null;
      clear_icon?: boolean;
      description?: string;
      autopilot?: "disabled" | "enabled" | "paused";
    }) => api.updateSpace(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["spaces"] });
      qc.invalidateQueries({ queryKey: ["space", id] });
      invalidateBoards(qc);
    },
  });
}

export function useLinkSpaceRepo(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      repo_url: string;
      branch: string;
      share_cronos: boolean;
    }) => api.linkSpaceRepo(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["spaces"] });
      qc.invalidateQueries({ queryKey: ["space", id] });
    },
  });
}

export function useUnlinkSpaceRepo(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.unlinkSpaceRepo(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["spaces"] });
      qc.invalidateQueries({ queryKey: ["space", id] });
    },
  });
}

export function useDeleteSpace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, cascade = false }: { id: string; cascade?: boolean }) =>
      api.deleteSpace(id, cascade),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["spaces"] });
      qc.invalidateQueries({ queryKey: ["activity"] });
      invalidateBoards(qc);
    },
  });
}

export function useSpaceTools(spaceId: string | null) {
  return useQuery({
    queryKey: ["space-tools", spaceId],
    queryFn: () => api.spaceTools(spaceId!),
    enabled: !!spaceId,
    staleTime: 30_000,
  });
}

export function useToolContent(spaceId: string | null, path: string | null, scope: string | null) {
  return useQuery({
    queryKey: ["tool-content", spaceId, path, scope],
    queryFn: () => api.toolContent(spaceId!, path!, scope!),
    enabled: !!spaceId && !!path && !!scope,
    staleTime: 60_000,
  });
}

export function useDiscoverySources() {
  return useQuery({
    queryKey: ["discovery", "sources"],
    queryFn: () => api.discoverySources(),
    staleTime: 60_000,
  });
}

export function useDiscoveryTools(kind?: string) {
  return useQuery({
    queryKey: ["discovery", "tools", { kind }],
    queryFn: () => api.discoveryTools(kind),
    staleTime: 60_000,
  });
}

export function useDiscoveryRefresh() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.discoveryRefresh(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["discovery", "sources"] });
      qc.invalidateQueries({ queryKey: ["discovery", "tools"] });
    },
  });
}

export function useAdoptTool(spaceId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { source_slug: string; kind: string; name: string }) => {
      if (!spaceId) throw new Error("No space selected");
      return api.adoptTool(spaceId, body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["space-tools", spaceId] });
      qc.invalidateQueries({ queryKey: ["discovery", "tools"] });
    },
  });
}

export function useUnadoptTool(spaceId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kind, name }: { kind: string; name: string }) => {
      if (!spaceId) throw new Error("No space selected");
      return api.unadoptTool(spaceId, kind, name);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["space-tools", spaceId] });
    },
  });
}

export function useToolTelemetry(
  spaceId: string | null,
  kind: string | null,
  name: string | null,
  window = "30d",
) {
  return useQuery({
    queryKey: ["tool-telemetry", spaceId, kind, name, window],
    queryFn: () => api.toolTelemetry(spaceId!, kind!, name!, window),
    enabled: !!spaceId && !!kind && !!name,
    staleTime: 60_000,
  });
}

export function useImportSpace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, renameTo }: { file: File; renameTo?: string }) =>
      api.importSpace(file, renameTo),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["spaces"] });
      qc.invalidateQueries({ queryKey: ["activity"] });
      invalidateBoards(qc);
    },
  });
}
