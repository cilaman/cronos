import typography from "@tailwindcss/typography";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surfaces — deep, forest-shadow neutrals with a green undertone.
        // `pitch` is the canvas; the numbered shades are elevated layers.
        pitch: {
          DEFAULT: "#0c1110", // page background
          50: "#141a17",      // raised surface (lanes, cards)
          100: "#1c2521",     // hover / secondary surface
          200: "#27322c",     // pressed / tertiary
        },
        hairline: {
          DEFAULT: "#252e29", // standard divider
          strong: "#3a4540",  // emphasised border
        },
        // Type — bone / paper warmed, never pure white.
        bone: {
          DEFAULT: "#ece6d7", // primary
          muted: "#a8ad9f",   // secondary
          faint: "#6b7066",   // tertiary / disabled
        },
        // Accent — anchored on the PWA theme color #215732.
        // Use `moss` for chrome (links, focus rings, headings). `moss.deep`
        // is the original PWA hex; reserve it for seals and heavy fills.
        moss: {
          DEFAULT: "#3d8f5a",
          bright: "#5ab578",  // hover
          deep: "#215732",    // PWA anchor — seals, heavy panels
          darker: "#163b22",  // pressed / inset
        },
        // Supporting accents (non-state chrome only — do NOT use for badges).
        brass: "#c89b3c",
        oxblood: "#8c3a3a",
      },
      boxShadow: {
        // Hairline highlight on top of dark cards (1px white at 4%).
        "inset-hairline": "inset 0 1px 0 0 rgb(255 255 255 / 0.04)",
        // Heavy lift for modals / popovers on the pitch canvas.
        lift: "0 8px 24px -8px rgb(0 0 0 / 0.6), 0 2px 4px -2px rgb(0 0 0 / 0.4)",
        // Soft phosphor glow for focused accent elements.
        "moss-glow": "0 0 0 1px rgb(61 143 90 / 0.4), 0 0 16px -2px rgb(61 143 90 / 0.25)",
      },
      backgroundImage: {
        // SVG grain — use as `bg-grain` overlay (low opacity) on flat surfaces.
        grain:
          "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.5 0'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='0.18'/></svg>\")",
        // Hairline grid — pair with `bg-[length:24px_24px]` (or `bg-grid-sm`).
        "hairline-grid":
          "linear-gradient(to right, rgb(255 255 255 / 0.03) 1px, transparent 1px), linear-gradient(to bottom, rgb(255 255 255 / 0.03) 1px, transparent 1px)",
        // Vignette for board edges.
        "pitch-vignette":
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
