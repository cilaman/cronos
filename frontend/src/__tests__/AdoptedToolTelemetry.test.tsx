import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AdoptedToolTelemetry } from "../components/AdoptedToolTelemetry";

vi.mock("../api", () => ({
  api: {
    toolTelemetry: vi.fn(),
  },
}));

import { api } from "../api";
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockApi = api as any as { toolTelemetry: ReturnType<typeof vi.fn> };

function makeQC() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

function renderTelemetry(props: {
  spaceId?: string;
  kind?: string;
  name?: string;
  window?: string;
}) {
  const qc = makeQC();
  return render(
    <QueryClientProvider client={qc}>
      <AdoptedToolTelemetry
        spaceId={props.spaceId ?? "space-1"}
        kind={props.kind ?? "agent"}
        name={props.name ?? "my-agent"}
        window={props.window}
      />
    </QueryClientProvider>,
  );
}

describe("AdoptedToolTelemetry — strip renders with data", () => {
  beforeEach(() => {
    mockApi.toolTelemetry.mockResolvedValue({
      kind: "agent",
      name: "my-agent",
      calls: 42,
      errors: 2,
      avg_success_rate: 0.952,
      human_rescue_count: 1,
    });
  });

  it("shows call count in the strip", async () => {
    renderTelemetry({});
    await waitFor(() => expect(screen.getByTestId("call-count")).toBeInTheDocument());
    expect(screen.getByTestId("call-count").textContent).toMatch(/42/);
  });

  it("shows success rate in the strip", async () => {
    renderTelemetry({});
    await waitFor(() => expect(screen.getByTestId("call-count")).toBeInTheDocument());
    // SuccessBar renders the percentage
    expect(screen.getByText("95%")).toBeInTheDocument();
  });

  it("does not show detail panel before expanding", async () => {
    renderTelemetry({});
    await waitFor(() => expect(screen.getByTestId("call-count")).toBeInTheDocument());
    expect(screen.queryByTestId("telemetry-detail")).not.toBeInTheDocument();
  });
});

describe("AdoptedToolTelemetry — empty-history state", () => {
  beforeEach(() => {
    mockApi.toolTelemetry.mockResolvedValue({
      kind: "agent",
      name: "my-agent",
      calls: 0,
      errors: 0,
      avg_success_rate: 0,
      human_rescue_count: 0,
    });
  });

  it("shows 'No calls' message in strip when calls is 0", async () => {
    renderTelemetry({});
    await waitFor(() => expect(screen.getByTestId("no-calls")).toBeInTheDocument());
    expect(screen.getByTestId("no-calls").textContent).toMatch(/No calls/);
  });

  it("shows empty-history message in expanded panel", async () => {
    renderTelemetry({});
    await waitFor(() => expect(screen.getByTestId("no-calls")).toBeInTheDocument());

    await userEvent.click(screen.getByTestId("telemetry-strip"));
    expect(screen.getByTestId("empty-history")).toBeInTheDocument();
  });
});

describe("AdoptedToolTelemetry — expand/collapse", () => {
  beforeEach(() => {
    mockApi.toolTelemetry.mockResolvedValue({
      kind: "agent",
      name: "my-agent",
      calls: 10,
      errors: 1,
      avg_success_rate: 0.9,
      human_rescue_count: 0,
    });
  });

  it("detail panel is hidden by default", async () => {
    renderTelemetry({});
    await waitFor(() => expect(screen.getByTestId("call-count")).toBeInTheDocument());
    expect(screen.queryByTestId("telemetry-detail")).not.toBeInTheDocument();
  });

  it("clicking strip expands the detail panel", async () => {
    renderTelemetry({});
    await waitFor(() => expect(screen.getByTestId("call-count")).toBeInTheDocument());

    await userEvent.click(screen.getByTestId("telemetry-strip"));
    expect(screen.getByTestId("telemetry-detail")).toBeInTheDocument();
  });

  it("clicking strip again collapses the detail panel", async () => {
    renderTelemetry({});
    await waitFor(() => expect(screen.getByTestId("call-count")).toBeInTheDocument());

    const strip = screen.getByTestId("telemetry-strip");
    await userEvent.click(strip);
    expect(screen.getByTestId("telemetry-detail")).toBeInTheDocument();

    await userEvent.click(strip);
    expect(screen.queryByTestId("telemetry-detail")).not.toBeInTheDocument();
  });

  it("detail panel shows calls, error rate, and rescue count", async () => {
    renderTelemetry({});
    await waitFor(() => expect(screen.getByTestId("call-count")).toBeInTheDocument());

    await userEvent.click(screen.getByTestId("telemetry-strip"));
    const detail = screen.getByTestId("telemetry-detail");
    expect(detail).toHaveTextContent("10");
    expect(detail).toHaveTextContent("Rescues");
  });

  it("uses the provided window prop in the query", async () => {
    renderTelemetry({ window: "7d" });
    await waitFor(() => expect(mockApi.toolTelemetry).toHaveBeenCalled());
    expect(mockApi.toolTelemetry).toHaveBeenCalledWith("space-1", "agent", "my-agent", "7d");
  });
});

describe("AdoptedToolTelemetry — loading state", () => {
  it("shows loading indicator while the query is pending", async () => {
    // Arrange: never-resolving promise keeps the query in pending state.
    mockApi.toolTelemetry.mockReturnValue(new Promise(() => {}));

    // Act
    renderTelemetry({});

    // Assert: loading text shown, no call-count / no-calls yet.
    await waitFor(() => expect(screen.getByText(/loading/i)).toBeInTheDocument());
    expect(screen.queryByTestId("call-count")).not.toBeInTheDocument();
    expect(screen.queryByTestId("no-calls")).not.toBeInTheDocument();
  });
});

describe("AdoptedToolTelemetry — call count pluralization", () => {
  it("renders singular 'call' when there is exactly one call", async () => {
    // Arrange
    mockApi.toolTelemetry.mockResolvedValue({
      kind: "agent",
      name: "my-agent",
      calls: 1,
      errors: 0,
      avg_success_rate: 1,
      human_rescue_count: 0,
    });

    // Act
    renderTelemetry({});

    // Assert: "1 call" with no trailing "s".
    await waitFor(() => expect(screen.getByTestId("call-count")).toBeInTheDocument());
    expect(screen.getByTestId("call-count").textContent).toBe("1 call");
  });

  it("renders plural 'calls' for more than one call", async () => {
    // Arrange
    mockApi.toolTelemetry.mockResolvedValue({
      kind: "agent",
      name: "my-agent",
      calls: 2,
      errors: 0,
      avg_success_rate: 1,
      human_rescue_count: 0,
    });

    // Act
    renderTelemetry({});

    // Assert
    await waitFor(() => expect(screen.getByTestId("call-count")).toBeInTheDocument());
    expect(screen.getByTestId("call-count").textContent).toBe("2 calls");
  });
});

describe("AdoptedToolTelemetry — success-rate color thresholds", () => {
  function setRate(rate: number) {
    mockApi.toolTelemetry.mockResolvedValue({
      kind: "agent",
      name: "my-agent",
      calls: 10,
      errors: 0,
      avg_success_rate: rate,
      human_rescue_count: 0,
    });
  }

  it("uses green styling at the 0.9 boundary (>= 0.9)", async () => {
    // Arrange: 0.9 is the inclusive green boundary.
    setRate(0.9);

    // Act
    renderTelemetry({});

    // Assert: the percentage label carries the green text class.
    await waitFor(() => expect(screen.getByText("90%")).toBeInTheDocument());
    expect(screen.getByText("90%").className).toContain("text-green-600");
  });

  it("uses amber styling between 0.7 (inclusive) and 0.9 (exclusive)", async () => {
    // Arrange
    setRate(0.7);

    // Act
    renderTelemetry({});

    // Assert
    await waitFor(() => expect(screen.getByText("70%")).toBeInTheDocument());
    expect(screen.getByText("70%").className).toContain("text-amber-600");
  });

  it("uses danger styling below 0.7", async () => {
    // Arrange
    setRate(0.5);

    // Act
    renderTelemetry({});

    // Assert
    await waitFor(() => expect(screen.getByText("50%")).toBeInTheDocument());
    expect(screen.getByText("50%").className).toContain("text-danger");
  });
});

describe("AdoptedToolTelemetry — error breakdown in detail panel", () => {
  it("shows the error rate, error legend, and ok count when errors exist", async () => {
    // Arrange: 4 errors out of 20 calls -> 20% error rate, 16 ok.
    mockApi.toolTelemetry.mockResolvedValue({
      kind: "agent",
      name: "my-agent",
      calls: 20,
      errors: 4,
      avg_success_rate: 0.8,
      human_rescue_count: 3,
    });

    // Act
    renderTelemetry({});
    await waitFor(() => expect(screen.getByTestId("call-count")).toBeInTheDocument());
    await userEvent.click(screen.getByTestId("telemetry-strip"));

    // Assert: error rate computed from errors/calls, legends present.
    const detail = screen.getByTestId("telemetry-detail");
    expect(detail).toHaveTextContent("20%"); // error rate
    expect(detail).toHaveTextContent("4 err");
    expect(detail).toHaveTextContent("16 ok");
    expect(detail).toHaveTextContent("3"); // rescue count
  });

  it("omits the error legend when there are zero errors", async () => {
    // Arrange: clean run, no errors.
    mockApi.toolTelemetry.mockResolvedValue({
      kind: "agent",
      name: "my-agent",
      calls: 8,
      errors: 0,
      avg_success_rate: 1,
      human_rescue_count: 0,
    });

    // Act
    renderTelemetry({});
    await waitFor(() => expect(screen.getByTestId("call-count")).toBeInTheDocument());
    await userEvent.click(screen.getByTestId("telemetry-strip"));

    // Assert: ok legend present, no "err" legend, 0% error rate.
    const detail = screen.getByTestId("telemetry-detail");
    expect(detail).toHaveTextContent("8 ok");
    expect(detail).not.toHaveTextContent("err");
    expect(detail).toHaveTextContent("0%");
  });
});

describe("AdoptedToolTelemetry — accessibility", () => {
  beforeEach(() => {
    mockApi.toolTelemetry.mockResolvedValue({
      kind: "agent",
      name: "my-agent",
      calls: 5,
      errors: 0,
      avg_success_rate: 1,
      human_rescue_count: 0,
    });
  });

  it("reflects expansion state via aria-expanded", async () => {
    // Arrange
    renderTelemetry({});
    await waitFor(() => expect(screen.getByTestId("call-count")).toBeInTheDocument());
    const strip = screen.getByTestId("telemetry-strip");

    // Assert collapsed default
    expect(strip).toHaveAttribute("aria-expanded", "false");

    // Act + Assert expanded after click
    await userEvent.click(strip);
    expect(strip).toHaveAttribute("aria-expanded", "true");
  });
});
