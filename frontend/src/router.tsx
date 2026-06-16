import React, { Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import App from "./App";
import { ArchivedPage } from "./pages/ArchivedPage";
import { BoardPage } from "./pages/BoardPage";
import { DashboardPage } from "./pages/DashboardPage";
import { MemoryPage } from "./pages/MemoryPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { SpaceCreatePage } from "./pages/SpaceCreatePage";
import { SpaceSettingsPage } from "./pages/SpaceSettingsPage";
import { SpaceToolsPage } from "./pages/SpaceToolsPage";
import { StatsPage } from "./pages/StatsPage";
import { TreePage } from "./pages/TreePage";
import { HarnessRunsPage } from "./pages/HarnessRunsPage";
import { HarnessListPage } from "./pages/HarnessListPage";
import { HarnessesPage } from "./pages/HarnessesPage";
import { FeaturesPage } from "./pages/FeaturesPage";
import { FileBrowserPage } from "./pages/FileBrowserPage";

const HarnessEditor = React.lazy(() => import("./pages/HarnessEditor").then((m) => ({ default: m.HarnessEditor })));

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<App />}>
        <Route index element={<DashboardPage />} />
        <Route path="board" element={<BoardPage />} />
        <Route path="features" element={<FeaturesPage />} />
        <Route path="harnesses" element={<HarnessesPage />} />
        <Route path="archived" element={<ArchivedPage />} />
        <Route path="tools" element={<SpaceToolsPage />} />
        <Route path="memory" element={<MemoryPage />} />
        <Route path="spaces/new" element={<SpaceCreatePage />} />
        <Route path="stats" element={<StatsPage />} />
        <Route path="spaces/:spaceId" element={<BoardPage />} />
        <Route path="spaces/:spaceId/features" element={<FeaturesPage />} />
        <Route path="spaces/:spaceId/tree" element={<TreePage />} />
        <Route path="spaces/:spaceId/settings" element={<SpaceSettingsPage />} />
        <Route path="spaces/:spaceId/tools" element={<SpaceToolsPage />} />
        <Route path="spaces/:spaceId/files" element={<FileBrowserPage />} />
        <Route path="spaces/:spaceId/harnesses" element={<HarnessListPage />} />
        <Route path="spaces/:spaceId/harnesses/:name/runs" element={<HarnessRunsPage />} />
        <Route
          path="spaces/:spaceId/harnesses/:name/edit"
          element={
            <Suspense fallback={<div>Loading…</div>}>
              <HarnessEditor />
            </Suspense>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
