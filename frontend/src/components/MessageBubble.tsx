import { useRef, useState } from "react";
import { SourceCitations } from "./SourceCitations";
import { submitFeedback, speakText } from "../api/client";
import type { ChatMessage } from "../types";

interface Props {
  message: ChatMessage;
}

type PlaybackState = "idle" | "loading" | "playing";

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const [feedback, setFeedback] = useState<1 | -1 | null>(message.feedback ?? null);
  const [playback, setPlayback] = useState<PlaybackState>("idle");
  const audioRef = useRef<HTMLAudioElement | null>(null);

  async function handleFeedback(value: 1 | -1) {
    if (feedback !== null || !message.logId) return;
    setFeedback(value);
    try {
      await submitFeedback(message.logId, value);
    } catch {
      setFeedback(null); // revert on error
    }
  }

  async function handlePlayback() {
    if (playback === "playing") {
      audioRef.current?.pause();
      setPlayback("idle");
      return;
    }
    setPlayback("loading");
    try {
      const blob = await speakText(message.content);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => setPlayback("idle");
      audio.onerror = () => setPlayback("idle");
      await audio.play();
      setPlayback("playing");
    } catch {
      setPlayback("idle");
    }
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-5`}>
      <div className={`max-w-[72%] ${isUser ? "order-2" : "order-1"}`}>
        <div
          className="px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap"
          style={
            isUser
              ? { background: "var(--cds-sidebar)", color: "#fdfcfa", borderRadius: "16px 16px 4px 16px" }
              : { background: "var(--cds-surface)", color: "var(--cds-text-primary)", border: "1px solid var(--cds-border)", borderRadius: "4px 16px 16px 16px" }
          }
        >
          {message.content}
        </div>

        {!isUser && (
          <>
            <SourceCitations sources={message.sources} loopCount={message.loopCount} />
            <div className="flex items-center gap-2 mt-1.5">
              <button
                onClick={handlePlayback}
                disabled={playback === "loading"}
                title={playback === "playing" ? "Stop" : "Play aloud"}
                className="transition-opacity"
                style={{ opacity: playback === "idle" ? 0.7 : 1 }}
              >
                {playback === "loading" ? (
                  <svg className="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--cds-text-faint)" strokeWidth="2">
                    <path d="M21 12a9 9 0 1 1-6.219-8.56" strokeLinecap="round" />
                  </svg>
                ) : playback === "playing" ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="var(--cds-accent)" stroke="var(--cds-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="6" y="5" width="4" height="14" rx="1" />
                    <rect x="14" y="5" width="4" height="14" rx="1" />
                  </svg>
                ) : (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--cds-text-faint)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                    <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                  </svg>
                )}
              </button>
              {message.logId && (
                <>
                  <button
                    onClick={() => handleFeedback(1)}
                    disabled={feedback !== null}
                    title="Helpful"
                    className="transition-opacity"
                    style={{ opacity: feedback !== null && feedback !== 1 ? 0.3 : 1 }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill={feedback === 1 ? "#16a34a" : "none"} stroke={feedback === 1 ? "#16a34a" : "var(--cds-text-faint)"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z" />
                      <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
                    </svg>
                  </button>
                  <button
                    onClick={() => handleFeedback(-1)}
                    disabled={feedback !== null}
                    title="Not helpful"
                    className="transition-opacity"
                    style={{ opacity: feedback !== null && feedback !== -1 ? 0.3 : 1 }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill={feedback === -1 ? "#dc2626" : "none"} stroke={feedback === -1 ? "#dc2626" : "var(--cds-text-faint)"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z" />
                      <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
                    </svg>
                  </button>
                </>
              )}
            </div>
          </>
        )}

        <div className={`text-xs mt-1 ${isUser ? "text-right" : "text-left"}`} style={{ color: "var(--cds-text-faint)" }}>
          {new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </div>
      </div>
    </div>
  );
}
