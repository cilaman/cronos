import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "cronos-theme";

// The pre-React script in index.html has already applied `.dark` on <html> if
// needed (from localStorage or `prefers-color-scheme`). Initial state is read
// from the DOM so React never disagrees with the first paint.
function readInitial(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(readInitial);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");

    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      meta.setAttribute("content", theme === "dark" ? "#07100c" : "#fafaf7");
    }

    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // private mode / disabled storage — fail silently
    }
  }, [theme]);

  const toggle = () => setTheme((t) => (t === "dark" ? "light" : "dark"));
  return [theme, toggle];
}
