import { useState } from "react";
import { SpaceFilterDropdown } from "../components/SpaceFilterDropdown";
import { StickyToolbar } from "../components/ui/StickyToolbar";
import { TreeView } from "../components/TreeView";

export function ArchivedPage() {
  const [spaceFilter, setSpaceFilter] = useState<string | null>(null);

  return (
    <>
      <StickyToolbar>
        <h1 className="font-display text-[13px] font-semibold uppercase tracking-[0.18em] text-ink">
          Archived
        </h1>
        <SpaceFilterDropdown value={spaceFilter} onChange={setSpaceFilter} />
      </StickyToolbar>

      <TreeView archivedOnly={true} spaceId={spaceFilter} />
    </>
  );
}
