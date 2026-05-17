import { cn } from "../../utils/cn";

interface Props {
  children: React.ReactNode;
  className?: string;
}

export function StickyToolbar({ children, className }: Props) {
  return (
    <div
      className={cn(
        "sticky top-0 z-20 flex h-12 items-center justify-between border-b border-hairline bg-surface-1/95 px-4 backdrop-blur",
        className,
      )}
    >
      {children}
    </div>
  );
}
