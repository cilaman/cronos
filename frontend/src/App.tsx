import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Board } from "./components/Board";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex h-screen flex-col">
        <header className="flex items-center justify-between border-b border-hairline bg-pitch-50 px-4 py-3 shadow-inset-hairline">
          <h1 className="text-lg font-semibold tracking-tight text-bone">Cronos</h1>
          <p className="hidden text-sm text-bone-muted sm:block">
            Kanban for Claude Code agents
          </p>
        </header>
        <main className="min-h-0 flex-1 bg-pitch bg-hairline-grid bg-grid-md">
          <Board />
        </main>
      </div>
    </QueryClientProvider>
  );
}
