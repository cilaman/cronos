import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PageContainer } from "../PageContainer";

describe("PageContainer", () => {
  it("renders children", () => {
    render(
      <PageContainer>
        <p>Page body</p>
      </PageContainer>,
    );
    expect(screen.getByText("Page body")).toBeInTheDocument();
  });

  it("defaults to content width (max-w-[1280px])", () => {
    const { container } = render(
      <PageContainer>
        <span>content</span>
      </PageContainer>,
    );
    const div = container.firstChild as HTMLElement;
    expect(div.className).toContain("max-w-[1280px]");
    expect(div.className).not.toContain("max-w-[768px]");
  });

  it("applies content width when width='content'", () => {
    const { container } = render(
      <PageContainer width="content">
        <span>content</span>
      </PageContainer>,
    );
    const div = container.firstChild as HTMLElement;
    expect(div.className).toContain("max-w-[1280px]");
  });

  it("applies reading width when width='reading'", () => {
    const { container } = render(
      <PageContainer width="reading">
        <span>content</span>
      </PageContainer>,
    );
    const div = container.firstChild as HTMLElement;
    expect(div.className).toContain("max-w-[768px]");
    expect(div.className).not.toContain("max-w-[1280px]");
  });

  it("applies standard padding classes", () => {
    const { container } = render(
      <PageContainer>
        <span>x</span>
      </PageContainer>,
    );
    const div = container.firstChild as HTMLElement;
    expect(div.className).toContain("p-6");
    expect(div.className).toContain("mx-auto");
  });

  it("merges extra className", () => {
    const { container } = render(
      <PageContainer className="custom-class">
        <span>x</span>
      </PageContainer>,
    );
    const div = container.firstChild as HTMLElement;
    expect(div.className).toContain("custom-class");
  });
});
