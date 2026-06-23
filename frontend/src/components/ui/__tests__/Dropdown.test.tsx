import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Dropdown } from "../Dropdown";

const ITEMS = [
  { value: "board", label: "Board" },
  { value: "list", label: "List" },
  { value: "tree", label: "Tree" },
];

function renderDropdown(overrides: Partial<React.ComponentProps<typeof Dropdown>> = {}) {
  const props = {
    trigger: <button>Open menu</button>,
    items: ITEMS,
    onSelect: vi.fn(),
    open: true,
    onOpenChange: vi.fn(),
    ...overrides,
  };
  return { ...render(<Dropdown {...props} />), props };
}

describe("Dropdown", () => {
  it("renders the trigger element", () => {
    renderDropdown({ open: false });
    expect(screen.getByRole("button", { name: "Open menu" })).toBeInTheDocument();
  });

  it("does not render menu items when closed", () => {
    renderDropdown({ open: false });
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("renders menu items when open", () => {
    renderDropdown();
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Board" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "List" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Tree" })).toBeInTheDocument();
  });

  it("calls onSelect with item value when clicked", async () => {
    const onSelect = vi.fn();
    renderDropdown({ onSelect });
    await userEvent.click(screen.getByRole("menuitem", { name: "List" }));
    expect(onSelect).toHaveBeenCalledWith("list");
  });

  it("calls onOpenChange(false) after selecting an item", async () => {
    const onOpenChange = vi.fn();
    renderDropdown({ onOpenChange });
    await userEvent.click(screen.getByRole("menuitem", { name: "Board" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("closes on ESC key press", () => {
    const onOpenChange = vi.fn();
    renderDropdown({ onOpenChange });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("closes on outside click", () => {
    const onOpenChange = vi.fn();
    renderDropdown({ onOpenChange });
    fireEvent.mouseDown(document.body);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("calls onOpenChange(true) when trigger is clicked while closed", async () => {
    const onOpenChange = vi.fn();
    renderDropdown({ open: false, onOpenChange });
    await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
    expect(onOpenChange).toHaveBeenCalledWith(true);
  });

  it("does not call onSelect for disabled items", async () => {
    const onSelect = vi.fn();
    const items = [{ value: "x", label: "Disabled", disabled: true }];
    renderDropdown({ items, onSelect });
    const btn = screen.getByRole("menuitem", { name: "Disabled" });
    // Disabled button — click does nothing
    await userEvent.click(btn);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("applies the z-[20] class to the menu panel", () => {
    renderDropdown();
    const menu = screen.getByRole("menu");
    expect(menu.className).toContain("z-[20]");
  });

  it("aligns menu to right when align=right", () => {
    renderDropdown({ align: "right" });
    const menu = screen.getByRole("menu");
    expect(menu.className).toContain("right-0");
  });
});
