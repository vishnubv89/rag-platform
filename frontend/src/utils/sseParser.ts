import type { StreamEvent } from "../types";

/**
 * Parse a single SSE frame (the text after splitting on "\n\n").
 * Returns the parsed StreamEvent or null if the frame is empty / not a data line.
 */
export function parseSSEFrame(frame: string): StreamEvent | null {
  const line = frame.trim();
  if (!line.startsWith("data: ")) return null;
  const raw = line.slice(6).trim();
  if (!raw) return null;
  return JSON.parse(raw) as StreamEvent;
}

/**
 * Parse a raw SSE chunk (possibly containing multiple frames) appended to
 * a carry-over buffer.  Returns the parsed events and the leftover buffer
 * text that didn't end with "\n\n" yet.
 */
export function parseSSEChunk(
  buffer: string,
  newData: string,
): { events: StreamEvent[]; remaining: string } {
  const combined = buffer + newData;
  const parts = combined.split("\n\n");
  const remaining = parts.pop() ?? "";
  const events: StreamEvent[] = [];
  for (const part of parts) {
    const event = parseSSEFrame(part);
    if (event) events.push(event);
  }
  return { events, remaining };
}
