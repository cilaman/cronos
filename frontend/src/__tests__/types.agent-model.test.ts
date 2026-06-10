import { describe, it, expect } from "vitest";
import { AGENT_MODELS } from "../types";
import type { AgentModel } from "../types";

describe("AgentModel fable-5 support", () => {
  it("AGENT_MODELS includes fable-5 with label 'Fable 5'", () => {
    const entry = AGENT_MODELS.find((m) => m.value === "fable-5");
    expect(entry).toBeDefined();
    expect(entry?.label).toBe("Fable 5");
  });

  it("AGENT_MODELS fable-5 value satisfies AgentModel type", () => {
    const model: AgentModel = "fable-5";
    expect(model).toBe("fable-5");
  });

  it("AGENT_MODELS contains all expected models including fable-5", () => {
    const values = AGENT_MODELS.map((m) => m.value);
    expect(values).toContain("default");
    expect(values).toContain("sonnet");
    expect(values).toContain("opus");
    expect(values).toContain("haiku");
    expect(values).toContain("opus-4-8");
    expect(values).toContain("fable-5");
  });
});
