import { useNavigate } from "react-router-dom";
import { SpaceForm } from "../components/spaces/SpaceForm";
import { useCreateSpace } from "../hooks/useSpaces";
import { PageContainer } from "../components/ui/PageContainer";
import { PageHeader } from "../components/ui/PageHeader";

export function SpaceCreatePage() {
  const navigate = useNavigate();
  const createSpace = useCreateSpace();

  return (
    <PageContainer width="reading">
      <div className="space-y-8">
        <PageHeader
          breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "New space" }]}
          title="New space"
          subtitle="Spaces own their own tasks, workspaces, and configuration."
        />

        <SpaceForm
          mode="create"
          submitting={createSpace.isPending}
          error={createSpace.error?.message ?? null}
          onCancel={() => navigate(-1)}
          onSubmit={async (values) => {
            const space = await createSpace.mutateAsync({
              name: values.name,
              color: values.color,
              icon: values.icon,
              description: values.description,
              repo_url: values.repoUrl,
              branch: values.branch,
              share_cronos: values.shareCronos,
            });
            navigate(`/spaces/${space.id}`);
          }}
        />
      </div>
    </PageContainer>
  );
}
