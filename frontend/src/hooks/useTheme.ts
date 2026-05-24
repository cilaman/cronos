import { useEffect, useState } from "react";

export type Theme = "light" | "dark" | "neon";

export const THEMES: readonly Theme[] = ["light", "dark", "neon"] as const;

export const THEME_META: Record<Theme, { label: string; metaColor: string }> = {
  light: { label: "Light", metaColor: "#fafaf7" },
  dark:  { label: "Dark",  metaColor: "#07100c" },
  neon:  { label: "Neon",  metaColor: "#050314" },
};

const STORAGE_KEY = "cronos-theme";

// Neon mode applies both `.dark` (activates dark: Tailwind variants for badges
// etc.) and `.neon` (overrides CSS vars to the purple palette). The `.neon`
// rule in index.css comes after `.dark` so neon vars win on specificity ties.
function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  root.classList.remove("dark", "neon");
  if (theme === "dark") {
    root.classList.add("dark");
  } else if (theme === "neon") {
    root.classList.add("dark", "neon");
  }

  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", THEME_META[theme].metaColor);

  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // private mode / storage disabled — fail silently
  }
}

// The pre-React script in index.html has already applied classes on <html>
// from localStorage. Read initial state from DOM to avoid first-paint flash.
function readInitial(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "dark" || stored === "neon" || stored === "light") return stored;
  } catch {
    // private mode
  }
  const cl = document.documentElement.classList;
  if (cl.contains("neon")) return "neon";
  if (cl.contains("dark")) return "dark";
  return "light";
}

export function useTheme(): [Theme, (theme: Theme) => void] {
  const [theme, setThemeState] = useState<Theme>(readInitial);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  return [theme, setThemeState];
}
