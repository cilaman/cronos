import { useTheme, THEMES, THEME_META } from "../hooks/useTheme";
import type { Theme } from "../hooks/useTheme";

// Visual swatch preview for each theme: [canvas, surface, accent]
const SWATCH: Record<Theme, { canvas: string; surface: string; accent: string }> = {
  light: { canvas: "#fafaf7", surface: "#ffffff", accent: "#15803d" },
  dark:  { canvas: "#07100c", surface: "#111b1b", accent: "#4ade80" },
  neon:  { canvas: "#03071e", surface: "#080e34", accent: "#00d2ff" },
};

export function ThemePicker() {
  const [theme, setTheme] = useTheme();

  return (
    <div
      className="flex items-center gap-1.5"
      role="radiogroup"
      aria-label="Color theme"
    >
      {THEMES.map((t) => {
        const { canvas, surface, accent } = SWATCH[t];
        const isActive = theme === t;
        return (
          <button
            key={t}
            type="button"
            role="radio"
            aria-checked={isActive}
            aria-label={`${THEME_META[t].label} theme`}
            title={THEME_META[t].label}
            onClick={() => setTheme(t)}
            className={[
              "relative h-[22px] w-[22px] shrink-0 overflow-hidden rounded transition-all focus:outline-none focus-visible:ring-1 focus-visible:ring-accent",
              isActive
                ? "ring-2 ring-accent shadow-accent-glow scale-110"
                : "ring-1 ring-hairline hover:ring-hairline-strong hover:scale-105",
            ].join(" ")}
            style={{ backgroundColor: canvas }}
          >
            {/* Mini surface stripe */}
            <span
              aria-hidden
              className="absolute inset-x-0 top-0 h-[10px]"
              style={{ backgroundColor: surface }}
            />
            {/* Accent corner dot */}
            <span
              aria-hidden
              className="absolute bottom-[3px] right-[3px] h-[5px] w-[5px] rounded-full"
              style={{ backgroundColor: accent }}
            />
          </button>
        );
      })}
    </div>
  );
}
