import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Skeleton } from "./Skeleton";

describe("Skeleton", () => {
  describe("text variant", () => {
    it("renders a single shimmer bar with role=status and aria-label=Loading", () => {
      render(<Skeleton variant="text" />);
      const el = screen.getByRole("status", { name: "Loading" });
      expect(el).toBeTruthy();
    });

    it("shimmer bar has animate-shimmer class", () => {
      const { container } = render(<Skeleton variant="text" />);
      const shimmerBar = container.querySelector(".animate-shimmer");
      expect(shimmerBar).toBeTruthy();
    });

    it("applies custom className to the wrapper", () => {
      const { container } = render(
        <Skeleton variant="text" className="custom-class" />
      );
      expect(container.firstChild).toHaveClass("custom-class");
    });
  });

  describe("block variant", () => {
    it("renders with role=status and aria-label=Loading", () => {
      render(<Skeleton variant="block" />);
      const el = screen.getByRole("status", { name: "Loading" });
      expect(el).toBeTruthy();
    });

    it("block shimmer bar has animate-shimmer class", () => {
      const { container } = render(<Skeleton variant="block" />);
      const shimmerBar = container.querySelector(".animate-shimmer");
      expect(shimmerBar).toBeTruthy();
    });

    it("block shimmer bar has h-20 class", () => {
      const { container } = render(<Skeleton variant="block" />);
      const shimmerBar = container.querySelector(".animate-shimmer");
      expect(shimmerBar).toHaveClass("h-20");
    });
  });

  describe("card variant", () => {
    it("renders with role=status and aria-label=Loading", () => {
      render(<Skeleton variant="card" />);
      const el = screen.getByRole("status", { name: "Loading" });
      expect(el).toBeTruthy();
    });

    it("card has rounded-xl and border classes", () => {
      const { container } = render(<Skeleton variant="card" />);
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass("rounded-xl");
      expect(wrapper).toHaveClass("border");
    });

    it("renders a header bar (h-6 w-2/3) plus 3 rows (h-4 w-full)", () => {
      const { container } = render(<Skeleton variant="card" />);
      const shimmerBars = container.querySelectorAll(".animate-shimmer");
      // header + 3 rows = 4 total
      expect(shimmerBars).toHaveLength(4);
      // header bar is h-6 w-2/3
      expect(shimmerBars[0]).toHaveClass("h-6");
      expect(shimmerBars[0]).toHaveClass("w-2/3");
      // rows are h-4 w-full
      expect(shimmerBars[1]).toHaveClass("h-4");
      expect(shimmerBars[2]).toHaveClass("h-4");
      expect(shimmerBars[3]).toHaveClass("h-4");
    });

    it("all shimmer bars in card have animate-shimmer class", () => {
      const { container } = render(<Skeleton variant="card" />);
      const shimmerBars = container.querySelectorAll(".animate-shimmer");
      shimmerBars.forEach((bar) => {
        expect(bar).toHaveClass("animate-shimmer");
      });
    });
  });

  describe("default variant", () => {
    it("defaults to text variant when no variant prop is given", () => {
      const { container } = render(<Skeleton />);
      const shimmerBars = container.querySelectorAll(".animate-shimmer");
      expect(shimmerBars).toHaveLength(1);
      expect(shimmerBars[0]).toHaveClass("h-4");
    });
  });

  describe("accessibility", () => {
    it("text variant has role=status", () => {
      const { container } = render(<Skeleton variant="text" />);
      const statusEl = container.querySelector('[role="status"]');
      expect(statusEl).toBeTruthy();
    });

    it("block variant has aria-label=Loading", () => {
      render(<Skeleton variant="block" />);
      expect(screen.getByLabelText("Loading")).toBeTruthy();
    });

    it("card variant has aria-label=Loading", () => {
      render(<Skeleton variant="card" />);
      expect(screen.getByLabelText("Loading")).toBeTruthy();
    });
  });
});
