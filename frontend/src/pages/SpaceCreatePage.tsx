import { Link, useNavigate } from "react-router-dom";
import { SpaceForm } from "../components/spaces/SpaceForm";
import { useCreateSpace } from "../hooks/useSpaces";

export function SpaceCreatePage() {
  const navigate = useNavigate();
  const createSpace = useCreateSpace();

  return (
    <div className="mx-auto max-w-3xl space-y-8 p-6 lg:p-8">
      <header>
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-ink-faint">
          <Link to="/" className="hover:text-accent-bright">
            Dashboard
          </Link>{" "}
          / new space
        </p>
        <h1 className="font-display text-[22px] font-semibold uppercase tracking-[0.14em] text-ink">
          New space
        </h1>
        <p className="mt-1 text-sm text-ink-muted">
          Spaces own their own tasks, workspaces, and configuration.
        </p>
      </header>

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
          });
          navigate(`/spaces/${space.id}`);
        }}
      />
    </div>
  );
}
