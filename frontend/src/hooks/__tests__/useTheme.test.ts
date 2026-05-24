import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTheme, THEMES, THEME_META } from "../useTheme";
import type { Theme } from "../useTheme";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function getHtmlClasses() {
  return Array.from(document.documentElement.classList);
}

function setHtmlClass(...classes: string[]) {
  document.documentElement.classList.remove("dark", "neon");
  classes.forEach((c) => document.documentElement.classList.add(c));
}

function setStorage(value: string | null) {
  if (value === null) {
    localStorage.removeItem("cronos-theme");
  } else {
    localStorage.setItem("cronos-theme", value);
  }
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  document.documentElement.classList.remove("dark", "neon");
  localStorage.removeItem("cronos-theme");
});

afterEach(() => {
  document.documentElement.classList.remove("dark", "neon");
  localStorage.removeItem("cronos-theme");
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// THEMES constant and THEME_META shape
// ---------------------------------------------------------------------------

describe("THEMES / THEME_META exports", () => {
  it("contains exactly three themes in order", () => {
    expect(THEMES).toEqual(["light", "dark", "neon"]);
  });

  it("THEME_META has label and metaColor for every theme", () => {
    for (const t of THEMES) {
      expect(THEME_META[t]).toHaveProperty("label");
      expect(THEME_META[t]).toHaveProperty("metaColor");
      expect(typeof THEME_META[t].label).toBe("string");
      expect(typeof THEME_META[t].metaColor).toBe("string");
    }
  });
});

// ---------------------------------------------------------------------------
// Initial state — read from DOM / localStorage
// ---------------------------------------------------------------------------

describe("useTheme — initial state", () => {
  it("defaults to light when no stored preference and no class on html", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current[0]).toBe("light");
  });

  it("reads 'dark' from localStorage", () => {
    setStorage("dark");
    const { result } = renderHook(() => useTheme());
    expect(result.current[0]).toBe("dark");
  });

  it("reads 'neon' from localStorage", () => {
    setStorage("neon");
    const { result } = renderHook(() => useTheme());
    expect(result.current[0]).toBe("neon");
  });

  it("reads 'light' from localStorage explicitly", () => {
    setStorage("light");
    const { result } = renderHook(() => useTheme());
    expect(result.current[0]).toBe("light");
  });

  it("reads initial theme from DOM .dark class (no localStorage)", () => {
    setHtmlClass("dark");
    const { result } = renderHook(() => useTheme());
    expect(result.current[0]).toBe("dark");
  });

  it("reads initial theme from DOM .neon class (no localStorage)", () => {
    setHtmlClass("dark", "neon");
    const { result } = renderHook(() => useTheme());
    expect(result.current[0]).toBe("neon");
  });

  it("ignores unknown localStorage values and falls back to light", () => {
    setStorage("solarized");
    const { result } = renderHook(() => useTheme());
    expect(result.current[0]).toBe("light");
  });
});

// ---------------------------------------------------------------------------
// DOM class manipulation
// ---------------------------------------------------------------------------

describe("useTheme — DOM class management", () => {
  it("adds .dark when theme is set to dark", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current[1]("dark"));
    expect(getHtmlClasses()).toContain("dark");
    expect(getHtmlClasses()).not.toContain("neon");
  });

  it("adds .dark and .neon when theme is set to neon", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current[1]("neon"));
    expect(getHtmlClasses()).toContain("dark");
    expect(getHtmlClasses()).toContain("neon");
  });

  it("removes dark and neon classes when theme is set to light", () => {
    setHtmlClass("dark", "neon");
    const { result } = renderHook(() => useTheme());
    act(() => result.current[1]("light"));
    expect(getHtmlClasses()).not.toContain("dark");
    expect(getHtmlClasses()).not.toContain("neon");
  });

  it("clears .neon when switching from neon to dark", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current[1]("neon"));
    expect(getHtmlClasses()).toContain("neon");

    act(() => result.current[1]("dark"));
    expect(getHtmlClasses()).toContain("dark");
    expect(getHtmlClasses()).not.toContain("neon");
  });

  it("clears .dark when switching from dark to light", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current[1]("dark"));
    expect(getHtmlClasses()).toContain("dark");

    act(() => result.current[1]("light"));
    expect(getHtmlClasses()).not.toContain("dark");
  });
});

// ---------------------------------------------------------------------------
// localStorage persistence
// ---------------------------------------------------------------------------

describe("useTheme — localStorage", () => {
  it("persists dark to localStorage", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current[1]("dark"));
    expect(localStorage.getItem("cronos-theme")).toBe("dark");
  });

  it("persists neon to localStorage", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current[1]("neon"));
    expect(localStorage.getItem("cronos-theme")).toBe("neon");
  });

  it("persists light to localStorage", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current[1]("dark"));
    act(() => result.current[1]("light"));
    expect(localStorage.getItem("cronos-theme")).toBe("light");
  });

  it("survives when localStorage throws (private mode simulation)", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("SecurityError");
    });
    const { result } = renderHook(() => useTheme());
    // should not throw
    expect(() => act(() => result.current[1]("neon"))).not.toThrow();
    expect(result.current[0]).toBe("neon");
  });
});

// ---------------------------------------------------------------------------
// meta theme-color
// ---------------------------------------------------------------------------

describe("useTheme — meta theme-color", () => {
  function getMetaContent(): string | null {
    return document.querySelector('meta[name="theme-color"]')?.getAttribute("content") ?? null;
  }

  beforeEach(() => {
    // Ensure the meta tag exists for these tests
    if (!document.querySelector('meta[name="theme-color"]')) {
      const meta = document.createElement("meta");
      meta.name = "theme-color";
      meta.content = "#fafaf7";
      document.head.appendChild(meta);
    }
  });

  it("sets meta to neon color when theme is neon", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current[1]("neon"));
    expect(getMetaContent()).toBe(THEME_META.neon.metaColor);
  });

  it("sets meta to dark color when theme is dark", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current[1]("dark"));
    expect(getMetaContent()).toBe(THEME_META.dark.metaColor);
  });

  it("sets meta to light color when theme is light", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current[1]("light"));
    expect(getMetaContent()).toBe(THEME_META.light.metaColor);
  });
});

// ---------------------------------------------------------------------------
// setTheme function identity
// ---------------------------------------------------------------------------

describe("useTheme — return value", () => {
  it("returns a tuple of [Theme, setter function]", () => {
    const { result } = renderHook(() => useTheme());
    const [theme, setTheme] = result.current;
    expect(typeof theme).toBe("string");
    expect(typeof setTheme).toBe("function");
  });

  it("calling setTheme updates the returned theme value", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current[0]).toBe("light");

    act(() => result.current[1]("neon"));
    expect(result.current[0]).toBe("neon");

    act(() => result.current[1]("dark"));
    expect(result.current[0]).toBe("dark");

    act(() => result.current[1]("light"));
    expect(result.current[0]).toBe("light");
  });

  it("cycles through all themes correctly", () => {
    const { result } = renderHook(() => useTheme());
    const themeSequence: Theme[] = ["dark", "neon", "light", "dark"];

    for (const t of themeSequence) {
      act(() => result.current[1](t));
      expect(result.current[0]).toBe(t);
    }
  });
});
