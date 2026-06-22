import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { PageHeader } from "../PageHeader";

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("PageHeader", () => {
  // ── title ──────────────────────────────────────────────────────────────────

  it("renders title in an h1 with class text-title", () => {
    renderWithRouter(<PageHeader title="My Page" />);
    const h1 = screen.getByRole("heading", { level: 1, name: "My Page" });
    expect(h1).toBeInTheDocument();
    expect(h1.className).toContain("text-title");
  });

  it("h1 does not carry ad-hoc size classes (text-sm, text-lg, text-[22px], uppercase, tracking-wider)", () => {
    renderWithRouter(<PageHeader title="My Page" />);
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.className).not.toMatch(/\btext-sm\b/);
    expect(h1.className).not.toMatch(/\btext-lg\b/);
    expect(h1.className).not.toContain("text-[22px]");
    expect(h1.className).not.toContain("uppercase");
    expect(h1.className).not.toContain("tracking-wider");
    expect(h1.className).not.toContain("tracking-[");
  });

  // ── subtitle ───────────────────────────────────────────────────────────────

  it("renders subtitle when provided", () => {
    renderWithRouter(<PageHeader title="My Page" subtitle="A description" />);
    expect(screen.getByText("A description")).toBeInTheDocument();
  });

  it("does not render subtitle area when omitted", () => {
    renderWithRouter(<PageHeader title="My Page" />);
    // No extra div below h1 for subtitle
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.nextSibling).toBeNull();
  });

  // ── breadcrumbs ────────────────────────────────────────────────────────────

  it("renders breadcrumbs nav when breadcrumbs provided", () => {
    renderWithRouter(
      <PageHeader
        title="My Page"
        breadcrumbs={[{ label: "Home", href: "/" }, { label: "My Page" }]}
      />,
    );
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toBeInTheDocument();
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getAllByText("My Page").length).toBeGreaterThanOrEqual(1);
  });

  it("renders a Link for breadcrumbs with href", () => {
    renderWithRouter(
      <PageHeader
        title="Page"
        breadcrumbs={[{ label: "Home", href: "/home" }]}
      />,
    );
    const link = screen.getByRole("link", { name: "Home" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/home");
  });

  it("renders plain text for breadcrumbs without href", () => {
    renderWithRouter(
      <PageHeader
        title="Page"
        breadcrumbs={[{ label: "Section" }]}
      />,
    );
    expect(screen.getByText("Section")).toBeInTheDocument();
    // should not be a link
    expect(screen.queryByRole("link", { name: "Section" })).not.toBeInTheDocument();
  });

  it("does not render breadcrumb nav when breadcrumbs is empty array", () => {
    renderWithRouter(<PageHeader title="Page" breadcrumbs={[]} />);
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("does not render breadcrumb nav when breadcrumbs omitted", () => {
    renderWithRouter(<PageHeader title="Page" />);
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  // ── actions ────────────────────────────────────────────────────────────────

  it("renders up to 3 actions inline", () => {
    renderWithRouter(
      <PageHeader
        title="Page"
        actions={[
          <button key="a">A</button>,
          <button key="b">B</button>,
          <button key="c">C</button>,
        ]}
      />,
    );
    expect(screen.getByRole("button", { name: "A" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "B" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "C" })).toBeInTheDocument();
    expect(screen.queryByText("More")).not.toBeInTheDocument();
  });

  it("renders first 2 inline and a More disclosure for 4+ actions", () => {
    renderWithRouter(
      <PageHeader
        title="Page"
        actions={[
          <button key="a">Act1</button>,
          <button key="b">Act2</button>,
          <button key="c">Act3</button>,
          <button key="d">Act4</button>,
        ]}
      />,
    );
    expect(screen.getByRole("button", { name: "Act1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Act2" })).toBeInTheDocument();
    // More disclosure must be present
    expect(screen.getByText("More")).toBeInTheDocument();
    // Act3 and Act4 are inside the details element
    expect(screen.getByRole("button", { name: "Act3" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Act4" })).toBeInTheDocument();
  });

  it("renders no action area when actions is empty", () => {
    const { container } = renderWithRouter(<PageHeader title="Page" actions={[]} />);
    // Right column should not be present (no actions)
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(container.querySelectorAll("span").length).toBe(0);
  });

  it("renders no action area when actions omitted", () => {
    renderWithRouter(<PageHeader title="Page" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  // ── sticky ─────────────────────────────────────────────────────────────────

  it("applies sticky classes when sticky=true", () => {
    const { container } = renderWithRouter(
      <PageHeader title="Sticky" sticky />,
    );
    const header = container.firstChild as HTMLElement;
    expect(header.className).toContain("sticky");
    expect(header.className).toContain("z-30");
    expect(header.className).toContain("backdrop-blur");
  });

  it("does not apply sticky classes when sticky=false (default)", () => {
    const { container } = renderWithRouter(<PageHeader title="Not Sticky" />);
    const header = container.firstChild as HTMLElement;
    expect(header.className).not.toContain("sticky");
    expect(header.className).not.toContain("z-30");
  });

  // ── className ──────────────────────────────────────────────────────────────

  it("merges extra className onto the header element", () => {
    const { container } = renderWithRouter(
      <PageHeader title="Page" className="extra-class" />,
    );
    const header = container.firstChild as HTMLElement;
    expect(header.className).toContain("extra-class");
  });

  // ── semantic markup ────────────────────────────────────────────────────────

  it("renders as a <header> element", () => {
    const { container } = renderWithRouter(<PageHeader title="Page" />);
    expect(container.firstChild?.nodeName).toBe("HEADER");
  });
});
