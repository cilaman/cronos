import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Menu } from "lucide-react";
import { Icon } from "./components/ui/Icon";
import { Sidebar } from "./components/Sidebar";

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="flex h-screen bg-canvas">
      {/* Mobile backdrop */}
      {menuOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
          onClick={() => setMenuOpen(false)}
        />
      )}

      {/* Sidebar wrapper — fixed drawer on mobile, static on desktop */}
      <div
        className={`fixed inset-y-0 left-0 z-50 transition-transform duration-200 ease-in-out lg:static lg:z-auto lg:translate-x-0 lg:transition-none ${
          menuOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <Sidebar onClose={() => setMenuOpen(false)} />
      </div>

      <div className="flex min-w-0 flex-1 flex-col overflow-x-hidden bg-canvas bg-hairline-grid bg-grid-md">
        {/* Mobile-only top bar */}
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-hairline bg-surface-1/95 px-4 backdrop-blur lg:hidden">
          <span className="font-display text-sm font-semibold uppercase tracking-[0.22em] text-ink">
            Cronos
          </span>
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            aria-label="Open navigation"
            className="rounded p-1.5 text-ink-muted transition hover:bg-surface-2 hover:text-ink"
          >
            <Icon icon={Menu} />
          </button>
        </header>

        <main className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
