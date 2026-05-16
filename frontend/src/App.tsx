import { Outlet } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";

export default function App() {
  return (
    <div className="flex h-screen bg-canvas">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col bg-canvas bg-hairline-grid bg-grid-md">
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
