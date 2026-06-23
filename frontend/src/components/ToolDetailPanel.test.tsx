import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { AiToolEntry } from "../types";

// ---------------------------------------------------------------------------
// Mock useToolContent from hooks/useSpaces
// ---------------------------------------------------------------------------
let mockIsLoading = false;
let mockIsError = false;
let mockData: { content: string } | undefined = undefined;

vi.mock("../hooks/useSpaces", () => ({
  useToolContent: () => ({
    data: mockData,
    isLoading: mockIsLoading,
    isError: mockIsError,
  }),
}));

// Mock formatRelative utility to avoid date-formatting complexity in tests
vi.mock("../utils/format", () => ({
  formatRelative: () => "just now",
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------
import { ToolDetailPanel } from "./ToolDetailPanel";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------
function makeTool(
  overrides: Partial<AiToolEntry & { category: "agent" | "command" | "skill" | "context" }> = {},
): AiToolEntry & { category: "agent" | "command" | "skill" | "context" } {
  return {
    name: "my-agent",
    path: ".claude/agents/my-agent.md",
    scope: "space",
    category: "agent",
    description: "An agent description",
    modified_at: "2026-01-01T00:00:00Z",
    type: "agent",
    ...overrides,
  } as AiToolEntry & { category: "agent" | "command" | "skill" | "context" };
}

function renderPanel(
  props: Partial<{ tool: ReturnType<typeof makeTool>; spaceId: string; onClose: () => void }> = {},
) {
  const onClose = props.onClose ?? vi.fn();
  const tool = props.tool ?? makeTool();
  const spaceId = props.spaceId ?? "space-1";
  const result = render(
    <ToolDetailPanel tool={tool} spaceId={spaceId} onClose={onClose} />,
  );
  return { ...result, onClose };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ToolDetailPanel — renders tool details", () => {
  beforeEach(() => {
    mockIsLoading = false;
    mockIsError = false;
    mockData = { content: "agent file content here" };
  });

  it("renders the tool name in the panel header", () => {
    renderPanel({ tool: makeTool({ name: "my-agent" }) });
    expect(screen.getByText("my-agent")).toBeInTheDocument();
  });

  it("renders tool description", () => {
    renderPanel({ tool: makeTool({ description: "An agent description" }) });
    expect(screen.getByText("An agent description")).toBeInTheDocument();
  });

  it("renders tool path in the metadata section", () => {
    renderPanel({ tool: makeTool({ path: ".claude/agents/my-agent.md" }) });
    expect(screen.getByText(".claude/agents/my-agent.md")).toBeInTheDocument();
  });

  it("renders file content when data is available", () => {
    mockData = { content: "agent file content here" };
    renderPanel();
    expect(screen.getByText("agent file content here")).toBeInTheDocument();
  });

  it("renders scope badge", () => {
    const { container } = renderPanel({ tool: makeTool({ scope: "space" }) });
    // ScopeBadge renders a <span> with font-mono tracking-[0.14em]; verify at least one exists
    const badge = container.querySelector("span.font-mono");
    expect(badge).toBeInTheDocument();
    expect(badge?.textContent).toBe("space");
  });

  it("renders 'No description' text when description is empty", () => {
    renderPanel({ tool: makeTool({ description: "" }) });
    expect(screen.getByText("No description")).toBeInTheDocument();
  });
});

describe("ToolDetailPanel — loading state shows Skeleton card", () => {
  beforeEach(() => {
    mockIsLoading = true;
    mockIsError = false;
    mockData = undefined;
  });

  it("shows a Skeleton (role=status, aria-label=Loading) when content is loading", () => {
    renderPanel();
    // Skeleton variant='card' renders [role=status][aria-label='Loading']
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
  });

  it("does NOT show an SVG animate-spin spinner when loading", () => {
    const { container } = renderPanel();
    // The old spinner used class animate-spin on an SVG; should not be present
    expect(container.querySelector(".animate-spin")).not.toBeInTheDocument();
  });

  it("shows shimmer bars (animate-shimmer) inside the Skeleton card", () => {
    const { container } = renderPanel();
    const shimmerBars = container.querySelectorAll(".animate-shimmer");
    expect(shimmerBars.length).toBeGreaterThan(0);
  });
});

describe("ToolDetailPanel — close behaviors", () => {
  beforeEach(() => {
    mockIsLoading = false;
    mockIsError = false;
    mockData = undefined;
  });

  it("calls onClose when the scrim (Modal backdrop) is clicked", () => {
    const { onClose } = renderPanel();
    // Modal renders a scrim with data-testid="modal-scrim"
    const scrim = screen.getByTestId("modal-scrim");
    fireEvent.click(scrim);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when Escape key is pressed", () => {
    const { onClose } = renderPanel();
    // Modal's keydown listener fires onClose on Escape
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when the 'Close panel' button is clicked", () => {
    const { onClose } = renderPanel();
    const closeBtn = screen.getByRole("button", { name: "Close panel" });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledOnce();
  });
});

describe("ToolDetailPanel — error state", () => {
  beforeEach(() => {
    mockIsLoading = false;
    mockIsError = true;
    mockData = undefined;
  });

  it("shows an error message when content fails to load", () => {
    renderPanel();
    expect(screen.getByText("Failed to load file content.")).toBeInTheDocument();
  });

  it("does not show Skeleton when in error state", () => {
    renderPanel();
    expect(screen.queryByRole("status", { name: "Loading" })).not.toBeInTheDocument();
  });
});
