import { cn } from "../../utils/cn";

interface Props {
  label: string;
  error?: string | null;
  className?: string;
  children: React.ReactNode;
}

export function FormField({ label, error, className, children }: Props) {
  return (
    <label className={cn("block", className)}>
      <span className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
        {label}
      </span>
      {children}
      {error && (
        <p className="mt-1 rounded border border-danger/40 bg-danger/15 px-2 py-1 text-xs text-danger">
          {error}
        </p>
      )}
    </label>
  );
}
