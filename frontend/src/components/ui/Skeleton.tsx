/**
 * Skeleton loading placeholder — three variants (text, block, card).
 *
 * The shimmer animation is provided by `.animate-shimmer` defined in
 * `frontend/src/index.css` (added in I1). That class sets:
 *   animation: shimmer 1400ms linear infinite;
 *   background-size: 200% 100%;
 *
 * Each shimmer bar must supply a `background-image` gradient so the
 * position animation is visible (I1 confirmed background-image is NOT
 * set by .animate-shimmer itself).
 */

const SHIMMER_GRADIENT =
  "linear-gradient(90deg, transparent 0%, rgb(255 255 255 / 0.12) 50%, transparent 100%)";

type SkeletonProps = {
  variant?: "text" | "block" | "card";
  className?: string;
};

function ShimmerBar({ className }: { className?: string }) {
  return (
    <div
      className={`animate-shimmer rounded bg-surface-2 ${className ?? ""}`}
      style={{ backgroundImage: SHIMMER_GRADIENT }}
    />
  );
}

export function Skeleton({ variant = "text", className }: SkeletonProps) {
  if (variant === "text") {
    return (
      <div
        role="status"
        aria-label="Loading"
        className={`w-full ${className ?? ""}`}
      >
        <ShimmerBar className="h-4 w-full" />
      </div>
    );
  }

  if (variant === "block") {
    return (
      <div
        role="status"
        aria-label="Loading"
        className={`w-full ${className ?? ""}`}
      >
        <ShimmerBar className="h-20 w-full" />
      </div>
    );
  }

  // card variant
  return (
    <div
      role="status"
      aria-label="Loading"
      className={`w-full rounded-xl border border-hairline p-4 ${className ?? ""}`}
    >
      {/* Header bar */}
      <ShimmerBar className="mb-4 h-6 w-2/3" />
      {/* Row 1 */}
      <ShimmerBar className="mb-2 h-4 w-full" />
      {/* Row 2 */}
      <ShimmerBar className="mb-2 h-4 w-full" />
      {/* Row 3 */}
      <ShimmerBar className="h-4 w-full" />
    </div>
  );
}

export default Skeleton;
