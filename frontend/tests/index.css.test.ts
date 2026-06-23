/**
 * index.css token presence tests (I1)
 *
 * Reads frontend/src/index.css as text and asserts that every new CSS variable
 * introduced in I1 (R1 status tokens, R2 categorical tokens, R3 brand tokens)
 * is defined inside each required theme block.
 *
 * No DOM/rendering: pure string-matching so the spec runs without a browser.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { join } from "path";

// Resolve path relative to this test file (frontend/tests/ → frontend/src/)
const cssPath = join(__dirname, "..", "src", "index.css");
const css = readFileSync(cssPath, "utf-8");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Extract the content of the first CSS block that starts with `selector {`
 * (single-level brace match — sufficient for flat @layer base blocks).
 */
function extractBlock(source: string, selector: string): string {
  const start = source.indexOf(selector);
  if (start === -1) throw new Error(`Selector "${selector}" not found in CSS`);
  const openBrace = source.indexOf("{", start);
  if (openBrace === -1) throw new Error(`Opening brace after "${selector}" not found`);

  let depth = 0;
  let i = openBrace;
  while (i < source.length) {
    if (source[i] === "{") depth++;
    else if (source[i] === "}") {
      depth--;
      if (depth === 0) return source.slice(openBrace + 1, i);
    }
    i++;
  }
  throw new Error(`Closing brace for "${selector}" not found`);
}

const rootBlock = extractBlock(css, ":root");
const darkBlock = extractBlock(css, ".dark");
const neonBlock = extractBlock(css, ".neon");

// ---------------------------------------------------------------------------
// R1: Status colour tokens — must appear in :root, .dark, and .neon
// ---------------------------------------------------------------------------

const statusTokens = [
  "--color-running",
  "--color-success",
  "--color-info",
  "--color-warning",
  "--color-danger",
  "--color-neutral",
] as const;

describe("R1: status colour tokens", () => {
  describe(":root block", () => {
    for (const token of statusTokens) {
      it(`defines ${token}`, () => {
        expect(rootBlock).toContain(token);
      });
    }
  });

  describe(".dark block", () => {
    for (const token of statusTokens) {
      it(`defines ${token}`, () => {
        expect(darkBlock).toContain(token);
      });
    }
  });

  describe(".neon block", () => {
    for (const token of statusTokens) {
      it(`defines ${token}`, () => {
        expect(neonBlock).toContain(token);
      });
    }
  });
});

// ---------------------------------------------------------------------------
// R2: Categorical tokens — must appear in :root, .dark, and .neon
// ---------------------------------------------------------------------------

const catTokens = [
  "--cat-goal",
  "--cat-feature",
  "--cat-fix",
  "--cat-issue",
  "--cat-plan",
  "--cat-ask",
] as const;

describe("R2: categorical tokens", () => {
  describe(":root block", () => {
    for (const token of catTokens) {
      it(`defines ${token}`, () => {
        expect(rootBlock).toContain(token);
      });
    }
  });

  describe(".dark block", () => {
    for (const token of catTokens) {
      it(`defines ${token}`, () => {
        expect(darkBlock).toContain(token);
      });
    }
  });

  describe(".neon block", () => {
    for (const token of catTokens) {
      it(`defines ${token}`, () => {
        expect(neonBlock).toContain(token);
      });
    }
  });
});

// ---------------------------------------------------------------------------
// R3: Brand identity tokens — theme-invariant, defined in :root only
// ---------------------------------------------------------------------------

const brandTokens = ["--brand", "--brand-deep", "--brand-light"] as const;

describe("R3: brand identity tokens in :root", () => {
  for (const token of brandTokens) {
    it(`defines ${token}`, () => {
      expect(rootBlock).toContain(token);
    });
  }
});

// ---------------------------------------------------------------------------
// R3 spot-checks: verify the brand violet triplet is correct
// ---------------------------------------------------------------------------

describe("R3: brand violet triplet values", () => {
  it("--brand equals 122 79 176", () => {
    expect(rootBlock).toMatch(/--brand:\s*122 79 176/);
  });

  it("--brand-deep equals 90 50 140", () => {
    expect(rootBlock).toMatch(/--brand-deep:\s*90 50 140/);
  });

  it("--brand-light equals 180 140 220", () => {
    expect(rootBlock).toMatch(/--brand-light:\s*180 140 220/);
  });
});

// ---------------------------------------------------------------------------
// R1 risk Q1: neon --color-info must NOT collide with --color-accent-bright
// The accent-bright in neon is 90 230 255; info must be distinct (120 210 255).
// ---------------------------------------------------------------------------

describe("Q1: neon --color-info is distinct from --color-accent-bright", () => {
  it("neon --color-info is 120 210 255 (not 90 230 255)", () => {
    expect(neonBlock).toMatch(/--color-info:\s*120 210 255/);
  });
});

// ---------------------------------------------------------------------------
// Q2: dark and neon --color-warning / --color-danger updated to brand values
// ---------------------------------------------------------------------------

describe("Q2: dark theme warning/danger updated to brand-aligned values", () => {
  it("dark --color-warning is 255 166 46", () => {
    expect(darkBlock).toMatch(/--color-warning:\s*255 166 46/);
  });

  it("dark --color-danger is 255 110 92", () => {
    expect(darkBlock).toMatch(/--color-danger:\s*255 110 92/);
  });
});

describe("Q2: neon theme warning/danger updated to brand-aligned values", () => {
  it("neon --color-warning is 255 200 50", () => {
    expect(neonBlock).toMatch(/--color-warning:\s*255 200 50/);
  });

  it("neon --color-danger is 255 100 80", () => {
    expect(neonBlock).toMatch(/--color-danger:\s*255 100 80/);
  });
});
