import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, taskFileUrl } from "../api";
import { FileBrowser } from "./FileBrowser";

interface Props {
  taskId: string;
  /** Override the aside element's className for alternate layouts (e.g. mobile tab view) */
  className?: string;
}

export function FilesPanel({ taskId, className }: Props) {
  const queryClient = useQueryClient();
  const { data: files = [], isLoading } = useQuery({
    queryKey: ["task-files", taskId],
    queryFn: () => api.taskFiles(taskId),
    refetchInterval: 10_000,
  });

  const uploadMutation = useMutation({
    mutationFn: ({ file, subdir }: { file: File; subdir: string }) =>
      api.uploadTaskFile(taskId, file, subdir),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["task-files", taskId] });
    },
  });

  return (
    <aside className={className ?? "hidden flex-col border-t border-hairline bg-surface-1/30 lg:flex lg:w-72 lg:shrink-0 lg:border-l lg:border-t-0"}>
      <h3 className="shrink-0 px-4 pt-4 pb-2 font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
        Files
      </h3>
      <FileBrowser
        files={files}
        isLoading={isLoading}
        fileUrlBuilder={(path, dl) => taskFileUrl(taskId, path, dl)}
        onUpload={(file, subdir) => uploadMutation.mutateAsync({ file, subdir }).then(() => undefined)}
        uploadPending={uploadMutation.isPending}
      />
    </aside>
  );
}
