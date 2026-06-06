import { describe, it, expect } from "vitest";
import type {
  NodeType,
  Position,
  NodePort,
  HarnessNode,
  NodeRef,
  HarnessEdge,
  Harness,
} from "../types";

// ---------------------------------------------------------------------------
// NodeType coverage
// ---------------------------------------------------------------------------

describe("NodeType", () => {
  it("covers all 5 node types", () => {
    const validNodeTypes: NodeType[] = [
      "agent",
      "trigger",
      "decision",
      "wait",
      "aggregator",
    ];
    expect(validNodeTypes).toHaveLength(5);
    expect(validNodeTypes).toContain("agent");
    expect(validNodeTypes).toContain("trigger");
    expect(validNodeTypes).toContain("decision");
    expect(validNodeTypes).toContain("wait");
    expect(validNodeTypes).toContain("aggregator");
  });
});

// ---------------------------------------------------------------------------
// Harness object construction
// ---------------------------------------------------------------------------

describe("Harness", () => {
  it("can be constructed with the correct shape", () => {
    const pos: Position = { x: 100, y: 200 };
    expect(pos.x).toBe(100);
    expect(pos.y).toBe(200);

    const port: NodePort = {
      id: "port-1",
      label: "output",
      port_type: "output",
    };
    expect(port.port_type).toBe("output");

    // NodePort is kept for historical reference; HarnessNode.ports is now a dict
    void port;

    const node: HarnessNode = {
      id: "node-1",
      type: "agent",
      label: "My Agent",
      position: { x: 50, y: 75 },
      ports: { in: {}, out: {} },
      data: { agent_ref: "my-agent", prompt_template: "do the thing" },
    };
    expect(node.type).toBe("agent");
    expect(Object.keys(node.ports)).toContain("in");
    expect(node.data["agent_ref"]).toBe("my-agent");

    const harness: Harness = {
      name: "my-harness",
      description: "A test harness",
      nodes: [node],
      edges: [],
      variables: { key1: "value1" },
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:01:00Z",
      version: "1.0",
    };

    expect(harness.name).toBe("my-harness");
    expect(harness.nodes).toHaveLength(1);
    expect(harness.edges).toHaveLength(0);
    expect(harness.variables["key1"]).toBe("value1");
    expect(harness.version).toBe("1.0");
  });

  it("allows optional fields to be omitted", () => {
    const harness: Harness = {
      name: "minimal-harness",
      nodes: [],
      edges: [],
      variables: {},
    };

    expect(harness.name).toBe("minimal-harness");
    expect(harness.description).toBeUndefined();
    expect(harness.created_at).toBeUndefined();
    expect(harness.updated_at).toBeUndefined();
    expect(harness.version).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// HarnessEdge — nested NodeRef (not flat strings)
// ---------------------------------------------------------------------------

describe("HarnessEdge", () => {
  it("source and target are NodeRef objects with node_id and port_id", () => {
    const source: NodeRef = { node_id: "node-1", port_id: "port-out" };
    const target: NodeRef = { node_id: "node-2", port_id: "port-in" };

    const edge: HarnessEdge = {
      id: "edge-1",
      source,
      target,
      label: "goes to",
    };

    // Verify the edge source/target are NodeRef objects — NOT flat strings
    expect(typeof edge.source).toBe("object");
    expect(typeof edge.target).toBe("object");

    expect(edge.source.node_id).toBe("node-1");
    expect(edge.source.port_id).toBe("port-out");
    expect(edge.target.node_id).toBe("node-2");
    expect(edge.target.port_id).toBe("port-in");

    expect(edge.label).toBe("goes to");
  });

  it("label is optional on HarnessEdge", () => {
    const edge: HarnessEdge = {
      id: "edge-2",
      source: { node_id: "n1", port_id: "p1" },
      target: { node_id: "n2", port_id: "p2" },
    };

    expect(edge.label).toBeUndefined();
  });

  it("source and target are distinct nested objects (not the same reference)", () => {
    const edge: HarnessEdge = {
      id: "edge-3",
      source: { node_id: "nodeA", port_id: "portX" },
      target: { node_id: "nodeB", port_id: "portY" },
    };

    expect(edge.source).not.toBe(edge.target);
    expect(edge.source.node_id).not.toBe(edge.target.node_id);
  });
});

// ---------------------------------------------------------------------------
// NodePort port_type union
// ---------------------------------------------------------------------------

describe("NodePort", () => {
  it("accepts port_type 'input'", () => {
    const port: NodePort = { id: "p1", label: "In", port_type: "input" };
    expect(port.port_type).toBe("input");
  });

  it("accepts port_type 'output'", () => {
    const port: NodePort = { id: "p2", label: "Out", port_type: "output" };
    expect(port.port_type).toBe("output");
  });
});
