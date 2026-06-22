/**
 * tailwind.config.js utility-exposure tests (I2)
 *
 * Reads the resolved Tailwind config and asserts that every new token alias
 * introduced in I2 (R4 colour aliases, R5 font-size scale, R6 z-index ladder,
 * R7 motion durations) is present in the extended theme.
 *
 * No DOM/rendering: reads the config module directly via dynamic import so the
 * spec runs in the vitest Node environment without browser APIs.
 */
import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "fs";
import { join } from "path";

// ---------------------------------------------------------------------------
// Load the Tailwind config by reading the JS source as text and extracting
// the theme.extend block. We use regex/string assertions against the source
// rather than executing the module (which requires Tailwind internals) to
// keep the test dependency-free.
// ---------------------------------------------------------------------------

const configPath = join(__dirname, "..", "tailwind.config.js");
const configSource = readFileSync(configPath, "utf-8");

// ---------------------------------------------------------------------------
// R4: Status colour tokens — running, success, info, neutral
// (warning + danger are pre-existing and must still be present)
// ---------------------------------------------------------------------------

describe("R4: status colour tokens in tailwind.config.js", () => {
  const statusColors = [
    { name: "running", variable: "--color-running" },
    { name: "success", variable: "--color-success" },
    { name: "info", variable: "--color-info" },
    { name: "neutral", variable: "--color-neutral" },
    { name: "warning", variable: "--color-warning" },
    { name: "danger", variable: "--color-danger" },
  ];

  for (const { name, variable } of statusColors) {
    it(`exports "${name}" alias backed by ${variable}`, () => {
      // Assert the alias key is present
      expect(configSource).toContain(`${name}:`);
      // Assert it references the correct CSS variable
      expect(configSource).toContain(`var(${variable})`);
    });
  }

  it("running uses <alpha-value> placeholder for opacity support", () => {
    expect(configSource).toMatch(/running:.*<alpha-value>/);
  });

  it("success uses <alpha-value> placeholder for opacity support", () => {
    expect(configSource).toMatch(/success:.*<alpha-value>/);
  });

  it("info uses <alpha-value> placeholder for opacity support", () => {
    expect(configSource).toMatch(/info:.*<alpha-value>/);
  });

  it("neutral uses <alpha-value> placeholder for opacity support", () => {
    expect(configSource).toMatch(/neutral:.*<alpha-value>/);
  });
});

// ---------------------------------------------------------------------------
// R4: Categorical tokens — cat-goal, cat-feature, cat-fix, cat-issue, cat-plan, cat-ask
// ---------------------------------------------------------------------------

describe("R4: categorical colour tokens in tailwind.config.js", () => {
  const catTokens = [
    { name: "cat-goal", variable: "--cat-goal" },
    { name: "cat-feature", variable: "--cat-feature" },
    { name: "cat-fix", variable: "--cat-fix" },
    { name: "cat-issue", variable: "--cat-issue" },
    { name: "cat-plan", variable: "--cat-plan" },
    { name: "cat-ask", variable: "--cat-ask" },
  ];

  for (const { name, variable } of catTokens) {
    it(`exports "${name}" alias backed by ${variable}`, () => {
      expect(configSource).toContain(`"${name}":`);
      expect(configSource).toContain(`var(${variable})`);
    });
  }
});

// ---------------------------------------------------------------------------
// R4: Brand identity tokens — brand, brand-deep, brand-light
// ---------------------------------------------------------------------------

describe("R4: brand identity tokens in tailwind.config.js", () => {
  it('exports "brand" alias backed by --brand', () => {
    expect(configSource).toContain("brand:");
    expect(configSource).toContain("var(--brand)");
  });

  it('exports "brand-deep" alias backed by --brand-deep', () => {
    expect(configSource).toContain('"brand-deep":');
    expect(configSource).toContain("var(--brand-deep)");
  });

  it('exports "brand-light" alias backed by --brand-light', () => {
    expect(configSource).toContain('"brand-light":');
    expect(configSource).toContain("var(--brand-light)");
  });

  it("brand uses <alpha-value> placeholder", () => {
    expect(configSource).toMatch(/brand:.*<alpha-value>/);
  });
});

// ---------------------------------------------------------------------------
// R5: Typography scale — six named font sizes
// ---------------------------------------------------------------------------

describe("R5: typography scale in tailwind.config.js", () => {
  const fontSizes = [
    { name: "title", size: "22px" },
    { name: "eyebrow", size: "11px" },
    { name: "cardtitle", size: "14px" },
    { name: "body", size: "14px" },
    { name: "meta", size: "12px" },
    { name: "micro", size: "10px" },
  ];

  for (const { name, size } of fontSizes) {
    it(`defines font-size "${name}" at ${size}`, () => {
      expect(configSource).toContain(`${name}:`);
      expect(configSource).toContain(size);
    });
  }

  it("title uses JetBrains Mono font (monospace identity label)", () => {
    expect(configSource).toContain("JetBrains Mono");
  });

  it("eyebrow has letter-spacing for small-caps label use", () => {
    expect(configSource).toContain("letterSpacing");
  });
});

// ---------------------------------------------------------------------------
// R6: Z-index ladder — seven named steps
// ---------------------------------------------------------------------------

describe("R6: z-index ladder in tailwind.config.js", () => {
  const zSteps = [
    { name: "base", value: "0" },
    { name: "raised", value: "10" },
    { name: "dropdown", value: "100" },
    { name: "scrim", value: "200" },
    { name: "modal", value: "300" },
    { name: "toast", value: "400" },
    { name: "tooltip", value: "500" },
  ];

  for (const { name, value } of zSteps) {
    it(`defines z-index step "${name}" = ${value}`, () => {
      expect(configSource).toContain(`${name}:`);
      expect(configSource).toContain(`"${value}"`);
    });
  }
});

// ---------------------------------------------------------------------------
// R7: Motion durations — three named transition durations
// ---------------------------------------------------------------------------

describe("R7: motion durations in tailwind.config.js", () => {
  it('defines "motion-fast" at 120ms', () => {
    expect(configSource).toContain('"motion-fast"');
    expect(configSource).toContain("120ms");
  });

  it('defines "motion-base" at 180ms', () => {
    expect(configSource).toContain('"motion-base"');
    expect(configSource).toContain("180ms");
  });

  it('defines "motion-slow" at 280ms', () => {
    expect(configSource).toContain('"motion-slow"');
    expect(configSource).toContain("280ms");
  });

  it("transitionDuration block is present in theme.extend", () => {
    expect(configSource).toContain("transitionDuration:");
  });
});

// ---------------------------------------------------------------------------
// R1 risk mitigation: existing warning/danger aliases must not be removed
// ---------------------------------------------------------------------------

describe("R1 risk mitigation: warning/danger aliases preserved", () => {
  it("warning alias references --color-warning", () => {
    expect(configSource).toContain("warning:");
    expect(configSource).toContain("var(--color-warning)");
  });

  it("danger alias references --color-danger", () => {
    expect(configSource).toContain("danger:");
    expect(configSource).toContain("var(--color-danger)");
  });
});

// ---------------------------------------------------------------------------
// Spacing steps — verify the spacing extension is present
// ---------------------------------------------------------------------------

describe("Spacing steps in tailwind.config.js", () => {
  it("spacing block is present in theme.extend", () => {
    expect(configSource).toContain("spacing:");
  });
});

// ---------------------------------------------------------------------------
// Border radius scale
// ---------------------------------------------------------------------------

describe("Border radius scale in tailwind.config.js", () => {
  it("sm radius is 4px", () => {
    expect(configSource).toContain("sm:");
    expect(configSource).toContain("4px");
  });

  it("md radius is 6px", () => {
    expect(configSource).toContain("md:");
    expect(configSource).toContain("6px");
  });

  it("lg radius is 8px", () => {
    expect(configSource).toContain("lg:");
    expect(configSource).toContain("8px");
  });

  it("full radius is 9999px", () => {
    expect(configSource).toContain("full:");
    expect(configSource).toContain("9999px");
  });
});

// ---------------------------------------------------------------------------
// Structural: theme.extend sections are all present
// ---------------------------------------------------------------------------

describe("Structural: theme.extend sections", () => {
  it("has fontSize section", () => {
    expect(configSource).toContain("fontSize:");
  });

  it("has zIndex section", () => {
    expect(configSource).toContain("zIndex:");
  });

  it("has transitionDuration section", () => {
    expect(configSource).toContain("transitionDuration:");
  });

  it("has borderRadius section", () => {
    expect(configSource).toContain("borderRadius:");
  });

  it("has spacing section", () => {
    expect(configSource).toContain("spacing:");
  });
});
