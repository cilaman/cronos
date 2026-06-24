import { useState, useEffect } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { FeaturesBoard } from "../components/FeaturesBoard";
import { SpaceFilterDropdown } from "../components/SpaceFilterDropdown";
import { StickyToolbar } from "../components/ui/StickyToolbar";
import { Skeleton } from "../components/ui/Skeleton";
import { useSpaces } from "../hooks/useSpaces";

const LS_KEY = "cronos.features.lastSpaceId";

function ScopedFeaturesPage({ spaceId }: { spaceId: string }) {
  const { data } = useSpaces();
  const space = data?.spaces.find((s) => s.id === spaceId) ?? null;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <StickyToolbar>
        <h1 className="font-display text-[13px] font-semibold uppercase tracking-[0.18em] text-ink">
          {space ? space.name : "Features"}
        </h1>
      </StickyToolbar>
      <div className="min-h-0 flex-1 overflow-hidden">
        <FeaturesBoard spaceId={spaceId} />
      </div>
    </div>
  );
}

function GlobalFeaturesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { data, isLoading: spacesLoading } = useSpaces();
  const spaces = data?.spaces ?? [];

  const urlSpaceId = searchParams.get("space");

  const [selectedSpaceId, setSelectedSpaceId] = useState<string | null>(() => {
    if (urlSpaceId) return urlSpaceId;
    try {
      return localStorage.getItem(LS_KEY);
    } catch {
      return null;
    }
  });

  // Auto-select first space when nothing is selected and spaces are loaded
  useEffect(() => {
    if (selectedSpaceId !== null || spaces.length === 0) return;
    const first = spaces[0].id;
    setSelectedSpaceId(first);
    try { localStorage.setItem(LS_KEY, first); } catch { /* ignore */ }
    setSearchParams({ space: first }, { replace: true });
  }, [selectedSpaceId, spaces, setSearchParams]);

  // Validate URL param against known spaces once loaded
  useEffect(() => {
    if (spacesLoading || spaces.length === 0 || !urlSpaceId) return;
    const known = spaces.find((s) => s.id === urlSpaceId);
    if (!known) {
      const lsId = (() => { try { return localStorage.getItem(LS_KEY); } catch { return null; } })();
      const fallback = lsId && spaces.find((s) => s.id === lsId) ? lsId : spaces[0].id;
      setSelectedSpaceId(fallback);
      try { localStorage.setItem(LS_KEY, fallback); } catch { /* ignore */ }
      setSearchParams({ space: fallback }, { replace: true });
    }
  // Only run when spacesLoading transitions to false
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spacesLoading]);

  const handleSelectSpace = (id: string | null) => {
    if (!id) return; // Features always requires a space
    setSelectedSpaceId(id);
    try { localStorage.setItem(LS_KEY, id); } catch { /* ignore */ }
    setSearchParams({ space: id }, { replace: true });
  };

  const activeSpace = spaces.find((s) => s.id === selectedSpaceId) ?? null;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <StickyToolbar>
        <h1 className="font-display text-[13px] font-semibold uppercase tracking-[0.18em] text-ink">
          {activeSpace ? activeSpace.name : "Features"}
        </h1>
        <SpaceFilterDropdown
          value={selectedSpaceId}
          onChange={handleSelectSpace}
        />
      </StickyToolbar>

      {spacesLoading && (
        <div className="space-y-4 p-6">
          <Skeleton variant="card" />
          <Skeleton variant="card" />
          <Skeleton variant="card" />
        </div>
      )}

      {!spacesLoading && spaces.length === 0 && (
        <div className="flex h-full items-center justify-center p-8">
          <p className="text-ink-muted">
            No spaces yet.{" "}
            <a href="/app/spaces/new" className="text-accent-bright underline">
              Create a space
            </a>{" "}
            to get started.
          </p>
        </div>
      )}

      {!spacesLoading && spaces.length > 0 && selectedSpaceId && (
        <div className="min-h-0 flex-1 overflow-hidden">
          <FeaturesBoard spaceId={selectedSpaceId} />
        </div>
      )}

      {!spacesLoading && spaces.length > 0 && !selectedSpaceId && (
        <div className="flex h-full items-center justify-center p-8">
          <p className="text-ink-muted">Select a space from the dropdown above to view features.</p>
        </div>
      )}
    </div>
  );
}

export function FeaturesPage() {
  const { spaceId: routeSpaceId } = useParams<{ spaceId?: string }>();

  if (routeSpaceId) {
    return <ScopedFeaturesPage spaceId={routeSpaceId} />;
  }

  return <GlobalFeaturesPage />;
}
