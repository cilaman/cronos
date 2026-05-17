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
