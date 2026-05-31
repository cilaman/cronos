import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// We mock useBuildInfo so we control backend data without a real fetch.
vi.mock("../../hooks/useBuildInfo");

// Mock import.meta.env Vite vars. These are replaced below per test as needed.
vi.mock("../../components/BuildInfo", async () => {
  // Re-export the real module but with import.meta.env stubbed.
  // We actually import the module directly, so no re-export needed here.
  return vi.importActual("../../components/BuildInfo");
});

import { BuildInfo } from "../BuildInfo";
import { useBuildInfo } from "../../hooks/useBuildInfo";

const mockUseBuildInfo = vi.mocked(useBuildInfo);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  // Default: hook returns no data yet (loading state).
  mockUseBuildInfo.mockReturnValue({ data: undefined, isLoading: true } as ReturnType<typeof useBuildInfo>);
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BuildInfo", () => {
  it("Test 1: SHA null — no link, no commit text rendered", () => {
    mockUseBuildInfo.mockReturnValue({
      data: { commit_sha: null, build_time: null, repo_url: null },
      isLoading: false,
    } as ReturnType<typeof useBuildInfo>);

    render(<BuildInfo />);

    // No anchor link
    expect(screen.queryByRole("link")).toBeNull();
    // No commit SHA text visible
    expect(screen.queryByText(/[0-9a-f]{7}/)).toBeNull();
  });

  it("Test 2: SHA + repo_url non-null — link rendered with correct href", () => {
    const sha = "abc1234567890";
    const repoUrl = "https://github.com/owner/repo";
    mockUseBuildInfo.mockReturnValue({
      data: { commit_sha: sha, build_time: null, repo_url: repoUrl },
      isLoading: false,
    } as ReturnType<typeof useBuildInfo>);

    render(<BuildInfo />);

    const link = screen.getByRole("link");
    expect(link).toBeTruthy();
    expect(link.getAttribute("href")).toBe(`${repoUrl}/commit/${sha}`);
    expect(link.getAttribute("target")).toBe("_blank");
    // Link text should be the short SHA (first 7 chars)
    expect(link.textContent).toBe(sha.slice(0, 7));
  });

  it("Test 3: Loading state — component renders without crash (stable layout)", () => {
    mockUseBuildInfo.mockReturnValue({
      data: undefined,
      isLoading: true,
    } as ReturnType<typeof useBuildInfo>);

    // Should not throw
    const { container } = render(<BuildInfo />);

    // Root element should exist (reserves space even while loading)
    expect(container.firstChild).toBeTruthy();
    // No link during loading
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("Test 4: Backend and frontend times within 5 min — single timestamp line", () => {
    const backendTime = "2026-05-31T15:00:00Z";
    // Frontend time 2 minutes later — within threshold
    const frontendTime = "2026-05-31T15:02:00Z";

    vi.stubEnv("VITE_BUILD_TIME", frontendTime);
    vi.stubEnv("VITE_BUILD_COMMIT", "");
    vi.stubEnv("VITE_BUILD_REPO_URL", "");

    mockUseBuildInfo.mockReturnValue({
      data: { commit_sha: null, build_time: backendTime, repo_url: null },
      isLoading: false,
    } as ReturnType<typeof useBuildInfo>);

    render(<BuildInfo />);

    // Single "Built ..." line should be present
    const built = screen.getByText(/Built/);
    expect(built).toBeTruthy();

    // "API:" and "UI:" labels should NOT appear
    expect(screen.queryByText(/API:/)).toBeNull();
    expect(screen.queryByText(/UI:/)).toBeNull();

    vi.unstubAllEnvs();
  });

  it("Test 5: Backend and frontend times diverged >5 min — two labeled lines", () => {
    const backendTime = "2026-05-31T15:00:00Z";
    // Frontend time 10 minutes later — beyond threshold
    const frontendTime = "2026-05-31T15:10:00Z";

    vi.stubEnv("VITE_BUILD_TIME", frontendTime);
    vi.stubEnv("VITE_BUILD_COMMIT", "");
    vi.stubEnv("VITE_BUILD_REPO_URL", "");

    mockUseBuildInfo.mockReturnValue({
      data: { commit_sha: null, build_time: backendTime, repo_url: null },
      isLoading: false,
    } as ReturnType<typeof useBuildInfo>);

    render(<BuildInfo />);

    // Both "API:" and "UI:" labels should be present
    expect(screen.getByText(/API:/)).toBeTruthy();
    expect(screen.getByText(/UI:/)).toBeTruthy();

    // "Built" single line should NOT appear
    expect(screen.queryByText(/^Built/)).toBeNull();

    vi.unstubAllEnvs();
  });
});
