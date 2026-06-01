import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { BuildInfo } from "../types";

const FALLBACK: BuildInfo = {
  commit_sha: null,
  build_time: null,
  repo_url: null,
};

export function useBuildInfo() {
  return useQuery({
    queryKey: ["build-info"],
    queryFn: () => api.getInfo().catch(() => FALLBACK),
    staleTime: 5 * 60 * 1000,
  });
}
