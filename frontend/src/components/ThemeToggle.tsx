import { useTheme } from "../hooks/useTheme";
import type { Theme } from "../hooks/useTheme";

const CYCLE: Record<Theme, Theme> = { light: "dark", dark: "neon", neon: "light" };
const NEXT_LABEL: Record<Theme, string> = {
  light: "Switch to dark mode",
  dark:  "Switch to neon mode",
  neon:  "Switch to light mode",
};

export function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  return (
    <button
      type="button"
      onClick={() => setTheme(CYCLE[theme])}
      aria-label={NEXT_LABEL[theme]}
      title={NEXT_LABEL[theme]}
      className="inline-flex h-9 w-9 items-center justify-center rounded border border-hairline text-ink-muted transition hover:border-hairline-strong hover:bg-surface-2 hover:text-ink focus:outline-none focus-visible:ring-1 focus-visible:ring-accent sm:h-8 sm:w-8"
    >
      {theme === "light" && <MoonGlyph />}
      {theme === "dark"  && <NeonGlyph />}
      {theme === "neon"  && <SunGlyph />}
    </button>
  );
}

function SunGlyph() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" width="16" height="16" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  );
}

function MoonGlyph() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" width="16" height="16" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

// Spark/bolt glyph for neon theme
function NeonGlyph() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" width="16" height="16" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}
