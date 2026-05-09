/**
 * Unit tests for src/utils/sseParser.ts
 *
 * The SSE parser is the most critical piece of client-side streaming logic:
 * a bug here breaks the entire chat stream. Tests cover all boundary cases
 * that can occur when network chunks arrive at arbitrary boundaries.
 */
import { describe, it, expect } from "vitest";
import { parseSSEFrame, parseSSEChunk } from "../utils/sseParser";

// ---------------------------------------------------------------------------
// parseSSEFrame
// ---------------------------------------------------------------------------

describe("parseSSEFrame", () => {
  it("parses a well-formed token frame", () => {
    const event = parseSSEFrame('data: {"type":"token","content":"Hello"}');
    expect(event).toEqual({ type: "token", content: "Hello" });
  });

  it("parses a done frame", () => {
    const event = parseSSEFrame('data: {"type":"done","log_id":42}');
    expect(event).toEqual({ type: "done", log_id: 42 });
  });

  it("returns null for empty string", () => {
    expect(parseSSEFrame("")).toBeNull();
  });

  it("returns null for whitespace-only string", () => {
    expect(parseSSEFrame("   ")).toBeNull();
  });

  it("returns null for a line without 'data:' prefix", () => {
    expect(parseSSEFrame('event: ping')).toBeNull();
  });

  it("returns null when data value is empty", () => {
    expect(parseSSEFrame("data: ")).toBeNull();
  });

  it("handles leading/trailing whitespace around the frame", () => {
    const event = parseSSEFrame('  data: {"type":"token","content":"hi"}  ');
    expect(event).toEqual({ type: "token", content: "hi" });
  });
});

// ---------------------------------------------------------------------------
// parseSSEChunk — buffer management
// ---------------------------------------------------------------------------

describe("parseSSEChunk", () => {
  it("parses a single complete frame", () => {
    const { events, remaining } = parseSSEChunk(
      "",
      'data: {"type":"token","content":"A"}\n\n',
    );
    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ type: "token", content: "A" });
    expect(remaining).toBe("");
  });

  it("parses multiple frames in one chunk", () => {
    const raw =
      'data: {"type":"token","content":"A"}\n\n' +
      'data: {"type":"token","content":"B"}\n\n';
    const { events } = parseSSEChunk("", raw);
    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ type: "token", content: "A" });
    expect(events[1]).toEqual({ type: "token", content: "B" });
  });

  it("carries over incomplete frame into remaining", () => {
    // Frame boundary arrives in next chunk
    const { events, remaining } = parseSSEChunk(
      "",
      'data: {"type":"token","content":"A"}',
    );
    expect(events).toHaveLength(0);
    expect(remaining).toBe('data: {"type":"token","content":"A"}');
  });

  it("combines carry-over buffer with new data to complete a frame", () => {
    const partial = 'data: {"type":"token","content":"A"}';
    const { events, remaining } = parseSSEChunk(partial, "\n\n");
    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ type: "token", content: "A" });
    expect(remaining).toBe("");
  });

  it("skips empty frames between delimiters", () => {
    // Two consecutive \n\n produce an empty part — should be ignored
    const raw =
      'data: {"type":"token","content":"X"}\n\n\n\n' +
      'data: {"type":"done","log_id":1}\n\n';
    const { events } = parseSSEChunk("", raw);
    expect(events).toHaveLength(2);
  });

  it("handles a split that falls mid-JSON", () => {
    // chunk 1 carries half the JSON, chunk 2 finishes it
    const chunk1 = 'data: {"type":"token","con';
    const { events: e1, remaining: r1 } = parseSSEChunk("", chunk1);
    expect(e1).toHaveLength(0);

    const chunk2 = 'tent":"split"}\n\n';
    const { events: e2 } = parseSSEChunk(r1, chunk2);
    expect(e2).toHaveLength(1);
    expect(e2[0]).toEqual({ type: "token", content: "split" });
  });

  it("returns empty events and empty remaining for empty input", () => {
    const { events, remaining } = parseSSEChunk("", "");
    expect(events).toHaveLength(0);
    expect(remaining).toBe("");
  });
});
