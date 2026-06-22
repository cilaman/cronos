import { useState } from "react";
import { SpaceFilterDropdown } from "../components/SpaceFilterDropdown";
import { PageContainer } from "../components/ui/PageContainer";
import { PageHeader } from "../components/ui/PageHeader";
import { TreeView } from "../components/TreeView";

export function ArchivedPage() {
  const [spaceFilter, setSpaceFilter] = useState<string | null>(null);

  return (
    <>
      <PageContainer className="py-4 lg:py-4">
        <PageHeader
          title="Archived"
          actions={[
            <SpaceFilterDropdown
              key="space-filter"
              value={spaceFilter}
              onChange={setSpaceFilter}
            />,
          ]}
        />
      </PageContainer>

      <TreeView archivedOnly={true} spaceId={spaceFilter} />
    </>
  );
}
