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
import { TestReportsPage } from "./pages/TestReportsPage";
import { TreePage } from "./pages/TreePage";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<App />}>
        <Route index element={<DashboardPage />} />
        <Route path="board" element={<BoardPage />} />
        <Route path="tree" element={<TreePage />} />
        <Route path="archived" element={<ArchivedPage />} />
        <Route path="tools" element={<SpaceToolsPage />} />
        <Route path="stats" element={<StatsPage />} />
        <Route path="tests" element={<TestReportsPage />} />
        <Route path="memory" element={<MemoryPage />} />
        <Route path="spaces/new" element={<SpaceCreatePage />} />
        <Route path="spaces/:spaceId" element={<BoardPage />} />
        <Route path="spaces/:spaceId/tree" element={<TreePage />} />
        <Route path="spaces/:spaceId/settings" element={<SpaceSettingsPage />} />
        <Route path="spaces/:spaceId/tools" element={<SpaceToolsPage />} />
        <Route path="spaces/:spaceId/stats" element={<StatsPage />} />
        <Route path="spaces/:spaceId/tests" element={<TestReportsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
