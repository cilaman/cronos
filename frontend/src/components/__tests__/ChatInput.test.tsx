import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatInput } from "../ChatInput";

function renderInput(overrides: Partial<Parameters<typeof ChatInput>[0]> = {}) {
  return render(
    <ChatInput
      taskState="backlog"
      waitingQuestion={null}
      pendingCount={0}
      isSending={false}
      error={null}
      onSend={vi.fn()}
      {...overrides}
    />,
  );
}

describe("ChatInput — routeHint label", () => {
  it("does not render route hint when prop is absent", () => {
    renderInput();
    expect(screen.queryByText(/will route to/i)).toBeNull();
  });

  it("renders route hint when provided", () => {
    renderInput({ routeHint: "→ will route to: Child Task" });
    expect(screen.getByText("→ will route to: Child Task")).toBeDefined();
  });

  it("renders routeToast when provided", () => {
    renderInput({ routeToast: "Sent to Child Task" });
    expect(screen.getByText("Sent to Child Task")).toBeDefined();
  });

  it("does not render routeToast when null", () => {
    renderInput({ routeToast: null });
    expect(screen.queryByText(/Sent to/i)).toBeNull();
  });
});
