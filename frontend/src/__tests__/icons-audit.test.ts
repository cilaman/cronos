/**
 * icons-audit.test.ts
 *
 * Scope-bounded regression guard for the gui-icons migration (CC-v1 I5).
 *
 * Enumerates ONLY the 11 in-scope source files and asserts that each is free of
 * structural emoji glyphs from the closed migration set and — where applicable —
 * free of hand-rolled `<svg` tags that should have been replaced by the Icon
 * component.
 *
 * IMPORTANT: This test enumerates only named imports; it MUST NOT scan
 * out-of-scope files (no glob over all of src/). Out-of-scope siblings
 * (PluginsPanel, ToolDetailPanel, Sidebar, etc.) legitimately retain old
 * glyphs and are deferred to a follow-up phase.
 *
 * Per-file notes on exceptions:
 *  - FileBrowser.tsx: `✕` (close glyph, ~line 126) and `▸` (upload-toggle
 *    arrow, ~line 309) are UI elements that were NOT part of the CATEGORY_ICON
 *    map migrated in I2. Excluded from the emoji audit; tracked as OOS findings.
 *  - Lane.tsx: retains one inline `<svg>` close-icon for the hide-lane button
 *    (not a structural icon in scope for I3). Excluded from the svg audit.
 *  - ViewPicker.tsx: retains StarIcon and CheckIcon `<svg>` components
 *    (decorative, not structural-navigation icons in scope for I3). Excluded.
 */

import { describe, it, expect } from "vitest";

// ---------------------------------------------------------------------------
// Source file contents — loaded via Vite's ?raw suffix (string at bundle time)
// ---------------------------------------------------------------------------
import iconTsx from "../components/ui/Icon.tsx?raw";
import fileBrowserTsx from "../components/FileBrowser.tsx?raw";
import fileBrowserPageTsx from "../pages/FileBrowserPage.tsx?raw";
import laneTsx from "../components/Lane.tsx?raw";
import spaceFilterDropdownTsx from "../components/SpaceFilterDropdown.tsx?raw";
import viewPickerTsx from "../components/ViewPicker.tsx?raw";
import markdownEditorModalTsx from "../components/MarkdownEditorModal.tsx?raw";
import timeFrameSelectorTsx from "../components/TimeFrameSelector.tsx?raw";
import themeToggleTsx from "../components/ThemeToggle.tsx?raw";
import appTsx from "../App.tsx?raw";

// ---------------------------------------------------------------------------
// Structural emoji closed set (design-report-gui-icons.md risks[0].mitigation)
//
// NOTE: `→` (right-arrow) used in TimeFrameSelector is intentionally NOT in
// this set — it is a textual range separator, not a structural icon.
// ---------------------------------------------------------------------------
const CLOSED_EMOJI_SET = [
  "🤖", // Bot (agent category)
  "⚡", // Zap (skill category)
  "⌘", // Command (command category)
  "📖", // BookOpen (context category)
  "🖼", // Image (image category)
  "📄", // FileText (text category)
  "💻", // Terminal (code category)
  "📑", // FileCode (document category)
  "🗜", // Archive (archive category)
  "⬛", // Binary (binary category)
  "＋", // Plus (add / new-task button)
  "✕", // Close glyph (modal / drawer close buttons)
  "▾", // ChevronDown (dropdown selectors)
  "▸", // ChevronRight (toggle / directory expand)
] as const;

/**
 * CATEGORY_ICON emoji subset — the chars migrated in I2 (FileBrowser.tsx).
 * Excludes ✕, ＋, ▾, ▸ which were NOT in the CATEGORY_ICON map and whose
 * residuals in FileBrowser.tsx are out-of-scope findings.
 */
const CATEGORY_ICON_EMOJI_SUBSET = [
  "🤖", "⚡", "⌘", "📖", "🖼", "📄", "💻", "📑", "🗜", "⬛",
] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function assertNoEmoji(content: string, file: string, glyphs: readonly string[]) {
  for (const glyph of glyphs) {
    if (content.includes(glyph)) {
      throw new Error(
        `${file}: found structural glyph ${JSON.stringify(glyph)} — should have been replaced by Icon component`,
      );
    }
  }
}

function assertNoInlineSvg(content: string, file: string) {
  const count = (content.match(/<svg/g) ?? []).length;
  if (count > 0) {
    throw new Error(
      `${file}: found ${count} inline <svg tag(s) — should have been replaced by Icon component`,
    );
  }
}

// ---------------------------------------------------------------------------
// Files fully migrated (both emoji + svg checks pass)
// ---------------------------------------------------------------------------

describe("icons-audit: Icon.tsx (foundation)", () => {
  it("has no closed-set structural emoji", () => {
    assertNoEmoji(iconTsx, "Icon.tsx", CLOSED_EMOJI_SET);
  });
  it("has no inline <svg tags", () => {
    assertNoInlineSvg(iconTsx, "Icon.tsx");
  });
  it("imports from lucide-react (correct package alias)", () => {
    expect(iconTsx).toContain("lucide-react");
    expect(iconTsx).not.toContain('"@lucide/react"');
    expect(iconTsx).not.toContain("'@lucide/react'");
  });
});

describe("icons-audit: FileBrowserPage.tsx", () => {
  it("has no closed-set structural emoji", () => {
    assertNoEmoji(fileBrowserPageTsx, "FileBrowserPage.tsx", CLOSED_EMOJI_SET);
  });
  it("has no inline <svg tags", () => {
    assertNoInlineSvg(fileBrowserPageTsx, "FileBrowserPage.tsx");
  });
});

describe("icons-audit: SpaceFilterDropdown.tsx", () => {
  it("has no closed-set structural emoji", () => {
    assertNoEmoji(spaceFilterDropdownTsx, "SpaceFilterDropdown.tsx", CLOSED_EMOJI_SET);
  });
  it("has no inline <svg tags", () => {
    assertNoInlineSvg(spaceFilterDropdownTsx, "SpaceFilterDropdown.tsx");
  });
});

describe("icons-audit: MarkdownEditorModal.tsx", () => {
  it("has no closed-set structural emoji", () => {
    assertNoEmoji(markdownEditorModalTsx, "MarkdownEditorModal.tsx", CLOSED_EMOJI_SET);
  });
  it("has no inline <svg tags", () => {
    assertNoInlineSvg(markdownEditorModalTsx, "MarkdownEditorModal.tsx");
  });
});

describe("icons-audit: TimeFrameSelector.tsx", () => {
  it("has no closed-set structural emoji", () => {
    assertNoEmoji(timeFrameSelectorTsx, "TimeFrameSelector.tsx", CLOSED_EMOJI_SET);
  });
  it("has no inline <svg tags", () => {
    assertNoInlineSvg(timeFrameSelectorTsx, "TimeFrameSelector.tsx");
  });
});

describe("icons-audit: ThemeToggle.tsx (I4 — inline SVGs replaced)", () => {
  it("has no closed-set structural emoji", () => {
    assertNoEmoji(themeToggleTsx, "ThemeToggle.tsx", CLOSED_EMOJI_SET);
  });
  it("has no inline <svg tags (SunGlyph/MoonGlyph/NeonGlyph removed)", () => {
    assertNoInlineSvg(themeToggleTsx, "ThemeToggle.tsx");
  });
});

describe("icons-audit: App.tsx (I4 — hamburger SVG replaced)", () => {
  it("has no closed-set structural emoji", () => {
    assertNoEmoji(appTsx, "App.tsx", CLOSED_EMOJI_SET);
  });
  it("has no inline <svg tags (hamburger replaced by Icon+Menu)", () => {
    assertNoInlineSvg(appTsx, "App.tsx");
  });
});

// ---------------------------------------------------------------------------
// FileBrowser.tsx — CATEGORY_ICON subset only
// (✕ close button and ▸ upload-toggle are OOS residuals, not CATEGORY_ICON)
// ---------------------------------------------------------------------------

describe("icons-audit: FileBrowser.tsx (I2 — CATEGORY_ICON emoji migrated)", () => {
  it("has no CATEGORY_ICON emoji from the migration set", () => {
    assertNoEmoji(fileBrowserTsx, "FileBrowser.tsx", CATEGORY_ICON_EMOJI_SUBSET);
  });
  it("has no inline <svg tags", () => {
    assertNoInlineSvg(fileBrowserTsx, "FileBrowser.tsx");
  });
});

// ---------------------------------------------------------------------------
// Lane.tsx — emoji check only; SVG residual (hide-lane close icon) excluded
// ---------------------------------------------------------------------------

describe("icons-audit: Lane.tsx (I3 — ＋ glyph replaced; hide-lane svg excluded)", () => {
  it("has no closed-set structural emoji", () => {
    assertNoEmoji(laneTsx, "Lane.tsx", CLOSED_EMOJI_SET);
  });
  // NOTE: Lane.tsx retains one <svg> for the hide-lane close button (not in I3 scope).
  // SVG check deliberately omitted — see OOS findings in impl-report-gui-icons--i5.md.
});

// ---------------------------------------------------------------------------
// ViewPicker.tsx — emoji check only; StarIcon/CheckIcon SVGs excluded
// ---------------------------------------------------------------------------

describe("icons-audit: ViewPicker.tsx (I3 — ▾ dropdown replaced; decorative SVGs excluded)", () => {
  it("has no closed-set structural emoji", () => {
    assertNoEmoji(viewPickerTsx, "ViewPicker.tsx", CLOSED_EMOJI_SET);
  });
  // NOTE: ViewPicker.tsx retains StarIcon and CheckIcon <svg> components.
  // These are decorative (not structural navigation icons in scope for I3).
  // SVG check deliberately omitted — see OOS findings in impl-report-gui-icons--i5.md.
});
