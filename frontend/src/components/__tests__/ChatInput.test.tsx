import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
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

describe("ChatInput — sign-off affordance (waiting_kind='signoff')", () => {
  const signoffProps = {
    taskState: "waiting" as const,
    waitingQuestion: "Right thing to build?",
    waitingKind: "signoff",
  };

  it("shows Approve and Reject controls only for sign-off waits", () => {
    renderInput(signoffProps);
    expect(screen.getByRole("button", { name: "Approve" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Reject" })).toBeDefined();
    expect(screen.queryByRole("button", { name: "Send" })).toBeNull();
  });

  it("shows the plain Send button for ordinary waits", () => {
    renderInput({
      taskState: "waiting",
      waitingQuestion: "What next?",
      waitingKind: null,
    });
    expect(screen.getByRole("button", { name: "Send" })).toBeDefined();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Reject" })).toBeNull();
  });

  it("approve sends the draft with verdict=approve", () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    renderInput({ ...signoffProps, onSend });
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "ship it" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(onSend).toHaveBeenCalledWith("ship it", "approve");
  });

  it("approve without a note sends a default message", () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    renderInput({ ...signoffProps, onSend });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(onSend).toHaveBeenCalledWith("Approved.", "approve");
  });

  it("reject requires feedback text and sends verdict=reject", () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    renderInput({ ...signoffProps, onSend });
    const reject = screen.getByRole("button", { name: "Reject" });
    expect((reject as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "no — change X" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(onSend).toHaveBeenCalledWith("no — change X", "reject");
  });

  it("labels the banner as a sign-off request", () => {
    renderInput(signoffProps);
    expect(screen.getByText("Sign-off requested")).toBeDefined();
    expect(screen.getByText("Right thing to build?")).toBeDefined();
  });
});
