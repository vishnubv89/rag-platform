/**
 * Unit tests for src/components/MessageBubble.tsx
 *
 * Covers:
 *  - User bubble: no feedback buttons rendered
 *  - Assistant bubble without logId: no feedback buttons
 *  - Assistant bubble with logId: thumbs up/down visible and enabled
 *  - Clicking thumbs up calls submitFeedback(logId, 1)
 *  - Clicking thumbs down calls submitFeedback(logId, -1)
 *  - Buttons disabled after a vote
 *  - Optimistic vote reverts when submitFeedback rejects
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MessageBubble } from "../components/MessageBubble";
import type { ChatMessage } from "../types";

// ---------------------------------------------------------------------------
// Module mocks — prevent real network calls and simplify child components
// ---------------------------------------------------------------------------

vi.mock("../api/client", () => ({
  submitFeedback: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("../components/SourceCitations", () => ({
  SourceCitations: () => null,
}));

import { submitFeedback } from "../api/client";
const mockSubmitFeedback = submitFeedback as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: "test-id",
    role: "assistant",
    content: "Test answer",
    sourceChunkIds: [],
    sources: [],
    loopCount: 1,
    timestamp: new Date("2024-01-01T12:00:00"),
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("MessageBubble", () => {
  beforeEach(() => {
    mockSubmitFeedback.mockClear();
  });

  describe("user message", () => {
    it("renders the message content", () => {
      render(<MessageBubble message={makeMessage({ role: "user", content: "Hello!" })} />);
      expect(screen.getByText("Hello!")).toBeInTheDocument();
    });

    it("does not render feedback buttons for user messages", () => {
      render(<MessageBubble message={makeMessage({ role: "user", logId: 99 })} />);
      expect(screen.queryByTitle("Helpful")).toBeNull();
      expect(screen.queryByTitle("Not helpful")).toBeNull();
    });
  });

  describe("assistant message — no logId", () => {
    it("renders content", () => {
      render(<MessageBubble message={makeMessage({ content: "My answer" })} />);
      expect(screen.getByText("My answer")).toBeInTheDocument();
    });

    it("does not render feedback buttons when logId is absent", () => {
      render(<MessageBubble message={makeMessage({ logId: undefined })} />);
      expect(screen.queryByTitle("Helpful")).toBeNull();
      expect(screen.queryByTitle("Not helpful")).toBeNull();
    });
  });

  describe("assistant message — with logId", () => {
    it("renders both feedback buttons", () => {
      render(<MessageBubble message={makeMessage({ logId: 42 })} />);
      expect(screen.getByTitle("Helpful")).toBeInTheDocument();
      expect(screen.getByTitle("Not helpful")).toBeInTheDocument();
    });

    it("both buttons are enabled before any vote", () => {
      render(<MessageBubble message={makeMessage({ logId: 42 })} />);
      expect(screen.getByTitle("Helpful")).not.toBeDisabled();
      expect(screen.getByTitle("Not helpful")).not.toBeDisabled();
    });

    it("clicking thumbs up calls submitFeedback with (logId, 1)", async () => {
      render(<MessageBubble message={makeMessage({ logId: 42 })} />);
      fireEvent.click(screen.getByTitle("Helpful"));
      await waitFor(() => expect(mockSubmitFeedback).toHaveBeenCalledWith(42, 1));
    });

    it("clicking thumbs down calls submitFeedback with (logId, -1)", async () => {
      render(<MessageBubble message={makeMessage({ logId: 42 })} />);
      fireEvent.click(screen.getByTitle("Not helpful"));
      await waitFor(() => expect(mockSubmitFeedback).toHaveBeenCalledWith(42, -1));
    });

    it("both buttons are disabled after casting a vote", async () => {
      render(<MessageBubble message={makeMessage({ logId: 42 })} />);
      fireEvent.click(screen.getByTitle("Helpful"));
      await waitFor(() => expect(mockSubmitFeedback).toHaveBeenCalled());
      expect(screen.getByTitle("Helpful")).toBeDisabled();
      expect(screen.getByTitle("Not helpful")).toBeDisabled();
    });

    it("reverts optimistic vote when submitFeedback rejects", async () => {
      mockSubmitFeedback.mockRejectedValueOnce(new Error("network error"));
      render(<MessageBubble message={makeMessage({ logId: 42 })} />);

      fireEvent.click(screen.getByTitle("Helpful"));

      // After rejection the buttons should be re-enabled (feedback reset to null)
      await waitFor(() => expect(screen.getByTitle("Helpful")).not.toBeDisabled());
      expect(screen.getByTitle("Not helpful")).not.toBeDisabled();
    });

    it("does not call submitFeedback again after vote is cast", async () => {
      render(<MessageBubble message={makeMessage({ logId: 42 })} />);
      fireEvent.click(screen.getByTitle("Helpful"));
      await waitFor(() => expect(mockSubmitFeedback).toHaveBeenCalledTimes(1));

      // Try clicking thumbs up again — button is now disabled, click should not fire
      fireEvent.click(screen.getByTitle("Helpful"));
      expect(mockSubmitFeedback).toHaveBeenCalledTimes(1);
    });

    it("pre-populates feedback from message.feedback prop", () => {
      // Message already has a stored vote (e.g. loaded from history)
      render(<MessageBubble message={makeMessage({ logId: 42, feedback: 1 })} />);
      expect(screen.getByTitle("Helpful")).toBeDisabled();
      expect(screen.getByTitle("Not helpful")).toBeDisabled();
    });
  });
});
