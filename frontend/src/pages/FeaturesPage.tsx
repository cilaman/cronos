import { useState } from "react";
import { useParams } from "react-router-dom";
import { FeaturesBoard } from "../components/FeaturesBoard";
import { readBoardSpaceFilter } from "../lib/storage";

export function FeaturesPage() {
  const { spaceId: routeSpaceId } = useParams<{ spaceId?: string }>();

  // effectiveSpaceId = route param > persisted board-space-filter > null
  // When null: render explicit empty-state.
  const [persistedSpaceId] = useState<string | null>(() => readBoardSpaceFilter());
  const effectiveSpaceId: string | null = routeSpaceId ?? persistedSpaceId ?? null;

  if (effectiveSpaceId === null) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <p className="text-ink-muted">Pick a space from the sidebar</p>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <FeaturesBoard spaceId={effectiveSpaceId} />
    </div>
  );
}
