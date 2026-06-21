/**
 * Provenance display tests for InstalledPluginCard.
 * Verifies that marketplace source, installPath, and installedAt fields are rendered
 * with appropriate fallbacks for null/missing values.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import type { PluginsResponse } from "../types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockData: PluginsResponse | undefined = undefined;
let mockLoading = false;

vi.mock("../hooks/usePlugins", () => ({
  usePlugins: () => ({ data: mockData, isLoading: mockLoading }),
  useInstallPlugin: () => ({ mutate: vi.fn(), isPending: false }),
  useUninstallPlugin: () => ({ mutate: vi.fn(), isPending: false }),
  useEnablePlugin: () => ({ mutate: vi.fn(), isPending: false }),
  useDisablePlugin: () => ({ mutate: vi.fn(), isPending: false }),
  useAddMarketplace: () => ({ mutate: vi.fn(), isPending: false }),
  useRemoveMarketplace: () => ({ mutate: vi.fn(), isPending: false }),
}));

import { PluginsPanel } from "./PluginsPanel";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resp(overrides: Partial<PluginsResponse> = {}): PluginsResponse {
  return { installed: [], available: [], marketplaces: [], ...overrides };
}

function renderPanel() {
  return render(<PluginsPanel />);
}

beforeEach(() => {
  mockData = undefined;
  mockLoading = false;
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

// ---------------------------------------------------------------------------
// Provenance: source unknown fallback
// ---------------------------------------------------------------------------

describe("provenance — source label", () => {
  it("does not show 'source unknown' when marketplace is present", () => {
    mockData = resp({
      installed: [
        {
          id: "p1",
          name: "Plugin With Source",
          marketplace: "anthropic-core",
          version: null,
          scope: "user",
          enabled: true,
          components: [],
          installPath: null,
          installedAt: null,
          lastUpdated: null,
        },
      ],
    });
    renderPanel();
    expect(screen.getByText("anthropic-core")).toBeInTheDocument();
    expect(screen.queryByText(/source unknown/i)).not.toBeInTheDocument();
  });

  it("shows 'source unknown' fallback when marketplace is null", () => {
    mockData = resp({
      installed: [
        {
          id: "p2",
          name: "Plugin No Source",
          marketplace: null,
          version: null,
          scope: "user",
          enabled: true,
          components: [],
          installPath: null,
          installedAt: null,
          lastUpdated: null,
        },
      ],
    });
    renderPanel();
    expect(screen.getByText(/source unknown/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Provenance: installPath
// ---------------------------------------------------------------------------

describe("provenance — installPath", () => {
  it("renders install path when present", () => {
    mockData = resp({
      installed: [
        {
          id: "p3",
          name: "Plugin With Path",
          marketplace: "core",
          version: null,
          scope: "user",
          enabled: true,
          components: [],
          installPath: "/home/user/.claude/plugins/my-plugin",
          installedAt: null,
          lastUpdated: null,
        },
      ],
    });
    renderPanel();
    expect(screen.getByText("/home/user/.claude/plugins/my-plugin")).toBeInTheDocument();
  });

  it("does not render path row when installPath is null", () => {
    mockData = resp({
      installed: [
        {
          id: "p4",
          name: "Plugin No Path",
          marketplace: "core",
          version: null,
          scope: "user",
          enabled: true,
          components: [],
          installPath: null,
          installedAt: null,
          lastUpdated: null,
        },
      ],
    });
    renderPanel();
    expect(screen.queryByText(/^path:/)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Provenance: installedAt
// ---------------------------------------------------------------------------

describe("provenance — installedAt", () => {
  it("renders 'installed:' label when installedAt is present", () => {
    mockData = resp({
      installed: [
        {
          id: "p5",
          name: "Plugin With Date",
          marketplace: "core",
          version: null,
          scope: "user",
          enabled: true,
          components: [],
          installPath: null,
          installedAt: "2024-03-15T10:00:00Z",
          lastUpdated: null,
        },
      ],
    });
    renderPanel();
    expect(screen.getByText(/installed:/)).toBeInTheDocument();
  });

  it("does not render installed-at row when installedAt is null", () => {
    mockData = resp({
      installed: [
        {
          id: "p6",
          name: "Plugin No Date",
          marketplace: "core",
          version: null,
          scope: "user",
          enabled: true,
          components: [],
          installPath: null,
          installedAt: null,
          lastUpdated: null,
        },
      ],
    });
    renderPanel();
    expect(screen.queryByText(/installed:/)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// All provenance fields together
// ---------------------------------------------------------------------------

it("renders path and installed-at when both are present (with marketplace)", () => {
  mockData = resp({
    installed: [
      {
        id: "p7",
        name: "Full Plugin",
        marketplace: "anthropic-core",
        version: "2.0.0",
        scope: "user",
        enabled: true,
        components: [],
        installPath: "/root/.claude/plugins/full-plugin",
        installedAt: "2024-06-01T08:00:00Z",
        lastUpdated: null,
      },
    ],
  });
  renderPanel();
  expect(screen.getByText("anthropic-core")).toBeInTheDocument();
  expect(screen.getByText("/root/.claude/plugins/full-plugin")).toBeInTheDocument();
  expect(screen.getByText(/installed:/)).toBeInTheDocument();
  expect(screen.queryByText(/source unknown/i)).not.toBeInTheDocument();
});
