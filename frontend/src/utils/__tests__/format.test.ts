import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { formatRelative } from "../format";
import { formatClock, formatFullTimestamp } from "../../parse-history";

describe("formatRelative", () => {
  it("returns em-dash for null", () => {
    expect(formatRelative(null)).toBe("—");
  });

  it("returns em-dash for undefined", () => {
    expect(formatRelative(undefined)).toBe("—");
  });

  it("returns em-dash for invalid date string", () => {
    expect(formatRelative("not-a-date")).toBe("—");
  });

  it("returns 'just now' for timestamps within 60 seconds", () => {
    const now = new Date(Date.now() - 10_000).toISOString();
    expect(formatRelative(now)).toBe("just now");
  });

  it("returns minutes ago for timestamps 1–59 minutes old", () => {
    const twoMinutesAgo = new Date(Date.now() - 2 * 60_000).toISOString();
    expect(formatRelative(twoMinutesAgo)).toBe("2m ago");
  });

  it("returns hours ago for timestamps 1–23 hours old", () => {
    const threeHoursAgo = new Date(Date.now() - 3 * 3_600_000).toISOString();
    expect(formatRelative(threeHoursAgo)).toBe("3h ago");
  });

  it("returns days ago for timestamps 1–29 days old", () => {
    const fiveDaysAgo = new Date(Date.now() - 5 * 86_400_000).toISOString();
    expect(formatRelative(fiveDaysAgo)).toBe("5d ago");
  });
});

describe("formatClock", () => {
  it("formats a valid ISO timestamp as HH:MM:SS", () => {
    expect(formatClock("2025-03-15T14:30:05Z")).toBe("14:30:05");
  });

  it("zero-pads single-digit hours, minutes, seconds", () => {
    expect(formatClock("2025-03-15T09:05:03Z")).toBe("09:05:03");
  });

  it("returns the original string for an invalid date", () => {
    expect(formatClock("bad-date")).toBe("bad-date");
  });
});

describe("formatFullTimestamp", () => {
  it("returns the original string for an invalid date", () => {
    expect(formatFullTimestamp("nonsense")).toBe("nonsense");
  });

  it("returns a non-empty string for a valid ISO timestamp", () => {
    const result = formatFullTimestamp("2025-06-01T12:00:00Z");
    expect(result.length).toBeGreaterThan(0);
    expect(result).not.toBe("2025-06-01T12:00:00Z");
  });
});
