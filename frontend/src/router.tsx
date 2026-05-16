import { Route, Routes } from "react-router-dom";
import App from "./App";
import { BoardPage } from "./pages/BoardPage";
import { DashboardPage } from "./pages/DashboardPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { SpaceCreatePage } from "./pages/SpaceCreatePage";
import { SpaceSettingsPage } from "./pages/SpaceSettingsPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<App />}>
        <Route index element={<DashboardPage />} />
        <Route path="board" element={<BoardPage />} />
        <Route path="spaces/new" element={<SpaceCreatePage />} />
        <Route path="spaces/:spaceId" element={<BoardPage />} />
        <Route path="spaces/:spaceId/settings" element={<SpaceSettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
