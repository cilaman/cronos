import { cn } from "../../utils/cn";

/**
 * PageContainer — standard page body wrapper.
 *
 * Props:
 *   width    — 'content' (default): max-w-[1280px]
 *            — 'reading': max-w-[768px] (for settings, docs-heavy pages)
 *   className — merged via cn()
 *   children  — page body content
 *
 * Spacing: p-6 mobile, lg:p-8 desktop (4/8 rhythm per design-system §2.3).
 */
interface Props {
  width?: "content" | "reading";
  className?: string;
  children: React.ReactNode;
}

export function PageContainer({ width = "content", className, children }: Props) {
  return (
    <div
      className={cn(
        "mx-auto w-full p-6 lg:p-8",
        width === "reading" ? "max-w-[768px]" : "max-w-[1280px]",
        className,
      )}
    >
      {children}
    </div>
  );
}
