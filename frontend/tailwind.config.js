import typography from "@tailwindcss/typography";

/** @type {import('tailwindcss').Config} */
export default {
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
        // Surfaces — operator-console ink with a green undertone.
        // `canvas` is the page bg; numbered `surface` shades stack upward.
        canvas: "#07100c",
        surface: {
          1: "#11181b", // raised — lanes, cards, modals, headers, inputs
          2: "#1a2326", // hover / secondary surface
          3: "#243030", // pressed / tertiary
        },
        hairline: {
          DEFAULT: "#1f2a26", // standard 1px divider
          strong: "#324038", // emphasised border (form inputs, highlights)
        },
        // Ink — phosphor-bone text scale, brighter than the previous bone.
        // Named `ink-*` to avoid the `text-text` class collision.
        ink: {
          DEFAULT: "#e8f0e3", // primary (15.2:1 on canvas, AAA)
          muted: "#a8b8ad",   // secondary (7.6:1 on canvas, AAA)
          faint: "#7e8e83",   // tertiary / disabled (4.7:1 on canvas, AA)
        },
        // Accent — phosphor green. `accent-deep` preserves the PWA #215732 seal.
        accent: {
          DEFAULT: "#4ade80",
          bright: "#86efac", // hover
          dim: "#2a6e3e",    // pressed / inset
          deep: "#215732",   // PWA anchor — seals, heavy panels
        },
        // Semantic supporting colors (non-state chrome — do NOT use for badges).
        warning: "#d4a647", // queued status, shell-tool labels
        danger: "#a84a4a",  // errors, stop button
      },
      boxShadow: {
        // Hairline highlight on top of dark cards (1px white at 4%).
        "inset-hairline": "inset 0 1px 0 0 rgb(255 255 255 / 0.04)",
        // Heavy lift for modals / popovers on the canvas.
        lift: "0 8px 24px -8px rgb(0 0 0 / 0.6), 0 2px 4px -2px rgb(0 0 0 / 0.4)",
        // Phosphor glow for focused accent elements.
        "accent-glow": "0 0 0 1px rgb(74 222 128 / 0.4), 0 0 16px -2px rgb(74 222 128 / 0.25)",
      },
      backgroundImage: {
        // SVG grain — use as `bg-grain` overlay (low opacity) on flat surfaces.
        grain:
          "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.5 0'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='0.18'/></svg>\")",
        // Hairline grid — pair with `bg-[length:24px_24px]` (or `bg-grid-sm`).
        "hairline-grid":
          "linear-gradient(to right, rgb(255 255 255 / 0.03) 1px, transparent 1px), linear-gradient(to bottom, rgb(255 255 255 / 0.03) 1px, transparent 1px)",
        // Vignette for board edges.
        "canvas-vignette":
          "radial-gradient(ellipse at center, transparent 50%, rgb(0 0 0 / 0.4) 100%)",
      },
      backgroundSize: {
        "grid-sm": "24px 24px",
        "grid-md": "40px 40px",
      },
    },
  },
  plugins: [typography],
};
