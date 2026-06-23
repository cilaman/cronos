import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock useTheme so we control the current theme in tests.
const mockSetTheme = vi.fn();
let mockTheme = "light";

vi.mock("../../hooks/useTheme", () => ({
  useTheme: () => [mockTheme, mockSetTheme],
}));

import { ThemeToggle } from "../ThemeToggle";

describe("ThemeToggle", () => {
  beforeEach(() => {
    mockTheme = "light";
    mockSetTheme.mockClear();
  });

  it("renders a button with an accessible aria-label for light theme", () => {
    render(<ThemeToggle />);
    expect(screen.getByRole("button", { name: /switch to dark mode/i })).toBeInTheDocument();
  });

  it("renders a button with an accessible aria-label for dark theme", () => {
    mockTheme = "dark";
    render(<ThemeToggle />);
    expect(screen.getByRole("button", { name: /switch to neon mode/i })).toBeInTheDocument();
  });

  it("renders a button with an accessible aria-label for neon theme", () => {
    mockTheme = "neon";
    render(<ThemeToggle />);
    expect(screen.getByRole("button", { name: /switch to light mode/i })).toBeInTheDocument();
  });

  it("calls setTheme with 'dark' when light theme is active and button is clicked", async () => {
    mockTheme = "light";
    const user = userEvent.setup();
    render(<ThemeToggle />);
    await user.click(screen.getByRole("button"));
    expect(mockSetTheme).toHaveBeenCalledWith("dark");
  });

  it("calls setTheme with 'neon' when dark theme is active and button is clicked", async () => {
    mockTheme = "dark";
    const user = userEvent.setup();
    render(<ThemeToggle />);
    await user.click(screen.getByRole("button"));
    expect(mockSetTheme).toHaveBeenCalledWith("neon");
  });

  it("calls setTheme with 'light' when neon theme is active and button is clicked", async () => {
    mockTheme = "neon";
    const user = userEvent.setup();
    render(<ThemeToggle />);
    await user.click(screen.getByRole("button"));
    expect(mockSetTheme).toHaveBeenCalledWith("light");
  });

  it("renders an SVG icon (Lucide) inside the button", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button");
    const svg = button.querySelector("svg");
    expect(svg).not.toBeNull();
  });

  it("does not render any inline SVG with hand-rolled path data (uses Lucide)", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button");
    const svg = button.querySelector("svg");
    // Lucide SVGs carry the 'lucide' class
    expect(svg?.classList.contains("lucide")).toBe(true);
  });

  it("icon is aria-hidden (decorative)", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button");
    const svg = button.querySelector("svg");
    expect(svg?.getAttribute("aria-hidden")).toBe("true");
  });
});
