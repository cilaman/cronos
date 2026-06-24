/**
 * CronosMark — theme-aware inline SVG brand mark.
 *
 * Inlines the geometry from docs/ui-ux-review/brand/logo/cronos-mark-flat.svg
 * but replaces the three hardcoded fills with CSS-variable refs so the mark
 * adapts correctly across light, dark, and neon themes (design risk #2).
 *
 * Colour mapping (per design-report I4 mitigation):
 *   outer ring  #3B4757  → stroke="rgb(var(--color-hairline-strong))"
 *   middle ring #56657A  → stroke="rgb(var(--color-ink-faint))"
 *   inner ring + nodes + core #7A4FB0 → stroke/fill="rgb(var(--brand))"
 *
 * The brand violet triplet (122 79 176) is theme-invariant and defined in
 * :root only (frontend/src/index.css), so violet elements look identical
 * across all three themes.
 */

interface CronosMarkProps {
  /** Tailwind / inline class applied to the <svg> element. Defaults to "h-6 w-6". */
  className?: string;
  /** Accessible label for the mark (hidden text for screen-readers). */
  title?: string;
}

export function CronosMark({ className = "h-6 w-6", title = "Cronos mark" }: CronosMarkProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 280 280"
      className={className}
      aria-label={title}
      role="img"
      data-testid="cronos-mark"
    >
      <title>{title}</title>
      <g transform="translate(140 140)">
        {/* outer ring — adapts to hairline-strong (grey chrome) */}
        <circle
          r={100}
          fill="none"
          stroke="rgb(var(--color-hairline-strong))"
          strokeWidth={22}
        />
        {/* middle ring — adapts to ink-faint (muted chrome) */}
        <circle
          r={68}
          fill="none"
          stroke="rgb(var(--color-ink-faint))"
          strokeWidth={14}
        />
        {/* inner accent ring — brand violet, theme-invariant */}
        <circle
          r={42}
          fill="none"
          stroke="rgb(var(--brand))"
          strokeWidth={9}
        />
        {/* anchor nodes — brand violet */}
        <circle cx={0} cy={-100} r={10} fill="rgb(var(--brand))" />
        <circle cx={87} cy={50} r={10} fill="rgb(var(--brand))" />
        <circle cx={-87} cy={50} r={10} fill="rgb(var(--brand))" />
        {/* core — brand violet */}
        <circle r={18} fill="rgb(var(--brand))" />
      </g>
    </svg>
  );
}
