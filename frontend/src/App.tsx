import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Board } from "./components/Board";
import { ThemeToggle } from "./components/ThemeToggle";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex h-screen flex-col">
        <header className="flex items-center justify-between border-b border-hairline bg-surface-1 px-4 py-3 shadow-inset-hairline">
          <h1 className="font-display text-base font-semibold uppercase tracking-[0.18em] text-ink">
            Cronos
          </h1>
          <div className="flex items-center gap-3">
            <p className="hidden text-sm text-ink-muted sm:block">
              Kanban for Claude Code agents
            </p>
            <ThemeToggle />
          </div>
        </header>
        <main className="min-h-0 flex-1 bg-canvas bg-hairline-grid bg-grid-md">
          <Board />
        </main>
      </div>
    </QueryClientProvider>
  );
}
