import typography from "@tailwindcss/typography";

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '"Geist"',
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        display: [
          '"JetBrains Mono"',
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
        mono: [
          '"JetBrains Mono"',
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      colors: {
        // Theme-aware semantic tokens. Backed by CSS variables defined in
        // `src/index.css` under `:root` (light) and `.dark`. The `<alpha-value>`
        // placeholder lets Tailwind's opacity modifiers (`bg-canvas/40`) work.
        canvas: "rgb(var(--color-canvas) / <alpha-value>)",
        surface: {
          1: "rgb(var(--color-surface-1) / <alpha-value>)",
          2: "rgb(var(--color-surface-2) / <alpha-value>)",
          3: "rgb(var(--color-surface-3) / <alpha-value>)",
        },
        hairline: {
          DEFAULT: "rgb(var(--color-hairline) / <alpha-value>)",
          strong: "rgb(var(--color-hairline-strong) / <alpha-value>)",
        },
        ink: {
          DEFAULT: "rgb(var(--color-ink) / <alpha-value>)",
          muted: "rgb(var(--color-ink-muted) / <alpha-value>)",
          faint: "rgb(var(--color-ink-faint) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "rgb(var(--color-accent) / <alpha-value>)",
          bright: "rgb(var(--color-accent-bright) / <alpha-value>)",
          dim: "rgb(var(--color-accent-dim) / <alpha-value>)",
          deep: "rgb(var(--color-accent-deep) / <alpha-value>)",
        },
        warning: "rgb(var(--color-warning) / <alpha-value>)",
        danger: "rgb(var(--color-danger) / <alpha-value>)",
      },
      boxShadow: {
        "inset-hairline": "inset 0 1px 0 0 var(--shadow-inset-hairline)",
        lift: "0 8px 24px -8px var(--shadow-lift-outer), 0 2px 4px -2px var(--shadow-lift-inner)",
        "accent-glow":
          "0 0 0 1px rgb(var(--color-accent) / 0.4), 0 0 16px -2px rgb(var(--color-accent) / 0.25)",
        "neon-glow":
          "0 0 0 1px rgb(var(--color-accent) / 0.5), 0 0 20px -2px rgb(var(--color-accent) / 0.45), 0 0 48px -8px rgb(var(--color-accent) / 0.2)",
      },
      backgroundImage: {
        grain: "var(--bg-grain)",
        "hairline-grid": "var(--bg-hairline-grid)",
        "canvas-vignette":
          "radial-gradient(ellipse at center, transparent 50%, var(--shadow-lift-outer) 100%)",
      },
      backgroundSize: {
        "grid-sm": "24px 24px",
        "grid-md": "40px 40px",
      },
      transitionDuration: {
        slow: "280ms",
        base: "180ms",
      },
    },
  },
  plugins: [typography],
};
