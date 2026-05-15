import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Board } from "./components/Board";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex h-screen flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 shadow-sm">
          <h1 className="text-lg font-semibold text-slate-900">Cronos</h1>
          <p className="hidden text-sm text-slate-500 sm:block">
            Kanban for Claude Code agents
          </p>
        </header>
        <main className="min-h-0 flex-1 bg-slate-50">
          <Board />
        </main>
      </div>
    </QueryClientProvider>
  );
}
