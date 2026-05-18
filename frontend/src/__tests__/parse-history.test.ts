import { describe, it, expect } from "vitest";
import { parseHistory, type HistoryEntry } from "../parse-history";

// Helper: wrap a header + body in the backend's fenced format.
function entry(header: string, body: string): string {
  return "```\n" + header + "\n" + body + "\n```";
}

// Helper: assert a parsed item is a HistoryEntry, narrow the type, and return it.
function asHistory(item: ReturnType<typeof parseHistory>[number]): HistoryEntry {
  if (item.kind !== "history") {
    throw new Error(`expected history entry, got ${item.kind}`);
  }
  return item;
}

describe("parseHistory — agent metadata header", () => {
  it("parses an agent entry with run/model/mode metadata", () => {
    const raw = entry(
      "2024-01-15T14:30:45Z [agent] run=0 model=claude-sonnet-4-6 mode=auto",
      "hello world"
    );
    const items = parseHistory(raw);
    expect(items).toHaveLength(1);
    const h = asHistory(items[0]);
    expect(h.role).toBe("agent");
    expect(h.timestamp).toBe("2024-01-15T14:30:45Z");
    expect(h.body).toBe("hello world");
    expect(h.agentInfo).toEqual({
      runIndex: 0,
      model: "claude-sonnet-4-6",
      mode: "auto",
    });
  });

  it("parses a non-zero run index correctly", () => {
    const raw = entry(
      "2024-01-15T14:30:45Z [agent] run=7 model=opus mode=plan",
      "body"
    );
    const h = asHistory(parseHistory(raw)[0]);
    expect(h.agentInfo).toEqual({
      runIndex: 7,
      model: "opus",
      mode: "plan",
    });
  });

  it("is backwards-compatible: agent entry without metadata yields undefined agentInfo", () => {
    const raw = entry("2024-01-15T14:30:45Z [agent]", "legacy body");
    const h = asHistory(parseHistory(raw)[0]);
    expect(h.role).toBe("agent");
    expect(h.body).toBe("legacy body");
    expect(h.agentInfo).toBeUndefined();
  });

  it("user entries never carry agentInfo even when metadata-like trailing text appears", () => {
    const raw = entry("2024-01-15T14:30:45Z [user]", "asked a question");
    const h = asHistory(parseHistory(raw)[0]);
    expect(h.role).toBe("user");
    expect(h.agentInfo).toBeUndefined();
  });

  it("returns undefined agentInfo when one of run/model/mode is missing", () => {
    // Missing 'mode' key.
    const raw = entry(
      "2024-01-15T14:30:45Z [agent] run=2 model=sonnet",
      "incomplete"
    );
    const h = asHistory(parseHistory(raw)[0]);
    // Header was recognised (entry parsed as history), but metadata is rejected.
    expect(h.role).toBe("agent");
    expect(h.agentInfo).toBeUndefined();
  });

  it("returns undefined agentInfo when run is not numeric", () => {
    const raw = entry(
      "2024-01-15T14:30:45Z [agent] run=abc model=sonnet mode=auto",
      "bad"
    );
    const h = asHistory(parseHistory(raw)[0]);
    expect(h.agentInfo).toBeUndefined();
  });

  it("handles metadata keys in any order", () => {
    const raw = entry(
      "2024-01-15T14:30:45Z [agent] mode=ask model=haiku run=3",
      "body"
    );
    const h = asHistory(parseHistory(raw)[0]);
    expect(h.agentInfo).toEqual({
      runIndex: 3,
      model: "haiku",
      mode: "ask",
    });
  });

  it("tolerates multiple spaces between metadata pairs", () => {
    const raw = entry(
      "2024-01-15T14:30:45Z [agent]   run=1   model=sonnet   mode=auto",
      "body"
    );
    const h = asHistory(parseHistory(raw)[0]);
    expect(h.agentInfo).toEqual({
      runIndex: 1,
      model: "sonnet",
      mode: "auto",
    });
  });

  it("preserves model identifiers that contain hyphens, digits, and dots", () => {
    const raw = entry(
      "2024-01-15T14:30:45Z [agent] run=0 model=claude-sonnet-4-6-20250620 mode=auto",
      "body"
    );
    const h = asHistory(parseHistory(raw)[0]);
    expect(h.agentInfo?.model).toBe("claude-sonnet-4-6-20250620");
  });
});

describe("parseHistory — multi-entry streams with mixed metadata", () => {
  it("parses a user entry followed by an agent entry with metadata", () => {
    const raw =
      entry("2024-01-15T14:30:00Z [user]", "do the thing") +
      "\n\n" +
      entry(
        "2024-01-15T14:30:45Z [agent] run=0 model=sonnet mode=auto",
        "did the thing"
      );

    const items = parseHistory(raw);
    expect(items).toHaveLength(2);

    const user = asHistory(items[0]);
    expect(user.role).toBe("user");
    expect(user.body).toBe("do the thing");
    expect(user.agentInfo).toBeUndefined();

    const agent = asHistory(items[1]);
    expect(agent.role).toBe("agent");
    expect(agent.body).toBe("did the thing");
    expect(agent.agentInfo).toEqual({
      runIndex: 0,
      model: "sonnet",
      mode: "auto",
    });
  });

  it("parses successive agent entries with incrementing run indices", () => {
    const raw =
      entry(
        "2024-01-15T14:30:00Z [agent] run=0 model=sonnet mode=auto",
        "first"
      ) +
      "\n\n" +
      entry(
        "2024-01-15T14:31:00Z [agent] run=1 model=sonnet mode=auto",
        "second"
      ) +
      "\n\n" +
      entry(
        "2024-01-15T14:32:00Z [agent] run=2 model=opus mode=plan",
        "third"
      );

    const items = parseHistory(raw);
    expect(items).toHaveLength(3);
    expect(asHistory(items[0]).agentInfo?.runIndex).toBe(0);
    expect(asHistory(items[1]).agentInfo?.runIndex).toBe(1);
    expect(asHistory(items[2]).agentInfo?.runIndex).toBe(2);
    expect(asHistory(items[2]).agentInfo?.model).toBe("opus");
    expect(asHistory(items[2]).agentInfo?.mode).toBe("plan");
  });

  it("mixes legacy (no metadata) and new (with metadata) agent entries", () => {
    const raw =
      entry("2024-01-15T14:30:00Z [agent]", "legacy answer") +
      "\n\n" +
      entry(
        "2024-01-15T14:31:00Z [agent] run=1 model=sonnet mode=auto",
        "new answer"
      );

    const items = parseHistory(raw);
    expect(items).toHaveLength(2);
    expect(asHistory(items[0]).agentInfo).toBeUndefined();
    expect(asHistory(items[1]).agentInfo).toEqual({
      runIndex: 1,
      model: "sonnet",
      mode: "auto",
    });
  });

  it("preserves bodies containing nested ``` code fences", () => {
    const body = "here is code:\n```python\nprint('hi')\n```";
    const raw = entry(
      "2024-01-15T14:30:00Z [agent] run=0 model=sonnet mode=auto",
      body
    );

    const items = parseHistory(raw);
    expect(items).toHaveLength(1);
    const h = asHistory(items[0]);
    expect(h.body).toBe(body);
    expect(h.agentInfo?.runIndex).toBe(0);
  });

  it("returns [] for empty input", () => {
    expect(parseHistory("")).toEqual([]);
    expect(parseHistory("   \n  ")).toEqual([]);
  });
});
