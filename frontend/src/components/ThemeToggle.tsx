import { Sun, Moon, Zap } from "lucide-react";
import { Icon } from "./ui/Icon";
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
      {theme === "light" && <Icon icon={Moon} />}
      {theme === "dark"  && <Icon icon={Zap} />}
      {theme === "neon"  && <Icon icon={Sun} />}
    </button>
  );
}
