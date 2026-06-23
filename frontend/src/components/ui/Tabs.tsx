import { cn } from "../../utils/cn";

export interface TabItem {
  value: string;
  label: string;
}

interface TabsProps {
  items: TabItem[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

/**
 * Controlled tab bar primitive.
 * Canonicalizes the Detail.tsx active-underline pattern.
 * Use I5 (Detail.tsx migration) to swap in this component at call sites.
 */
export function Tabs({ items, value, onChange, className }: TabsProps) {
  return (
    <div
      role="tablist"
      className={cn("flex gap-4 border-b border-hairline", className)}
    >
      {items.map((item) => {
        const isActive = item.value === value;
        return (
          <button
            key={item.value}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(item.value)}
            className={cn(
              "relative pb-2 text-xs font-medium transition-colors",
              isActive
                ? "text-ink after:absolute after:inset-x-0 after:-bottom-px after:h-px after:bg-accent"
                : "text-ink-muted hover:text-ink",
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
