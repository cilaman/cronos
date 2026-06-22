/**
 * I3: favicon + PWA manifest wiring tests
 *
 * Reads index.html and public/site.webmanifest as text and asserts the
 * expected <link> elements and manifest content are present.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, it, expect } from "vitest";

const ROOT = resolve(__dirname, "..");

const indexHtml = readFileSync(resolve(ROOT, "index.html"), "utf-8");
const manifest = readFileSync(
  resolve(ROOT, "public", "site.webmanifest"),
  "utf-8"
);

describe("index.html favicon and manifest links", () => {
  it("contains SVG favicon link", () => {
    expect(indexHtml).toContain(
      'rel="icon" type="image/svg+xml" href="/cronos-favicon.svg"'
    );
  });

  it("contains PNG favicon link for 32x32", () => {
    expect(indexHtml).toContain(
      'rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png"'
    );
  });

  it("contains PNG favicon link for 16x16", () => {
    expect(indexHtml).toContain(
      'rel="icon" type="image/png" sizes="16x16" href="/favicon-16.png"'
    );
  });

  it("contains apple-touch-icon link", () => {
    expect(indexHtml).toContain(
      'rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon-180.png"'
    );
  });

  it("contains manifest link", () => {
    expect(indexHtml).toContain('rel="manifest" href="/site.webmanifest"');
  });
});

describe("site.webmanifest content", () => {
  it("declares app name as Cronos", () => {
    expect(manifest).toContain('"name": "Cronos"');
  });

  it("declares short_name as Cronos", () => {
    expect(manifest).toContain('"short_name": "Cronos"');
  });

  it("includes a 32x32 icon entry", () => {
    expect(manifest).toContain('"sizes": "32x32"');
  });

  it("includes a 512x512 icon entry", () => {
    expect(manifest).toContain('"sizes": "512x512"');
  });

  it("includes cronos-app-icon-512.png as 512x512 icon", () => {
    expect(manifest).toContain('"src": "/cronos-app-icon-512.png"');
  });

  it("is valid JSON", () => {
    expect(() => JSON.parse(manifest)).not.toThrow();
  });
});
