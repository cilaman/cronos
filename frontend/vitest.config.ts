import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/**/*.spec.{ts,tsx}",
        "src/test-setup.ts",
        "src/main.tsx",
      ],
      thresholds: {
        // Global ratchet — raise as more files gain tests.
        // Per-directory targets met: lib ≥80 hooks ≥50 ui ≥40 pages ≥30
        lines: 27,
      },
    },
  },
});
