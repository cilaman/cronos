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
        // R4: new status colour tokens (backed by I1 CSS variables)
        running: "rgb(var(--color-running) / <alpha-value>)",
        success: "rgb(var(--color-success) / <alpha-value>)",
        info: "rgb(var(--color-info) / <alpha-value>)",
        neutral: "rgb(var(--color-neutral) / <alpha-value>)",
        // R4: categorical tokens
        "cat-goal": "rgb(var(--cat-goal) / <alpha-value>)",
        "cat-feature": "rgb(var(--cat-feature) / <alpha-value>)",
        "cat-fix": "rgb(var(--cat-fix) / <alpha-value>)",
        "cat-issue": "rgb(var(--cat-issue) / <alpha-value>)",
        "cat-plan": "rgb(var(--cat-plan) / <alpha-value>)",
        "cat-ask": "rgb(var(--cat-ask) / <alpha-value>)",
        // R4: brand identity tokens (theme-invariant, :root only)
        brand: "rgb(var(--brand) / <alpha-value>)",
        "brand-deep": "rgb(var(--brand-deep) / <alpha-value>)",
        "brand-light": "rgb(var(--brand-light) / <alpha-value>)",
      },
      // R5: six-step typography scale
      fontSize: {
        title: ["22px", { lineHeight: "1.3", fontWeight: "700", fontFamily: '"JetBrains Mono", ui-monospace, monospace' }],
        eyebrow: ["11px", { lineHeight: "1.2", fontWeight: "600", letterSpacing: "0.08em" }],
        cardtitle: ["14px", { lineHeight: "1.4", fontWeight: "600" }],
        body: ["14px", { lineHeight: "1.5", fontWeight: "400" }],
        meta: ["12px", { lineHeight: "1.4", fontWeight: "400" }],
        micro: ["10px", { lineHeight: "1.3", fontWeight: "400" }],
      },
      // R6: seven-step z-index ladder
      zIndex: {
        base: "0",
        raised: "10",
        dropdown: "100",
        scrim: "200",
        modal: "300",
        toast: "400",
        tooltip: "500",
      },
      // R7: motion duration tokens
      transitionDuration: {
        "motion-fast": "120ms",
        "motion-base": "180ms",
        "motion-slow": "280ms",
      },
      // Spacing steps
      spacing: {
        "4": "4px",
        "8": "8px",
        "12": "12px",
        "16": "16px",
        "24": "24px",
        "32": "32px",
        "48": "48px",
      },
      // Border radius scale
      borderRadius: {
        sm: "4px",
        md: "6px",
        lg: "8px",
        full: "9999px",
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
    },
  },
  plugins: [typography],
};
