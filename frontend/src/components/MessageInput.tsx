import { useState, useRef, type KeyboardEvent } from "react";
import { useVoiceRecorder } from "../hooks/useVoiceRecorder";

interface Props {
  onSend: (text: string) => void;
  loading: boolean;
}

export function MessageInput({ onSend, loading }: Props) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const voice = useVoiceRecorder((transcribed) => {
    setText((prev) => (prev ? `${prev} ${transcribed}` : transcribed));
    textareaRef.current?.focus();
  });

  function submit() {
    if (!text.trim() || loading) return;
    onSend(text);
    setText("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  }

  function onInput() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }

  const recording = voice.state === "recording";
  const transcribing = voice.state === "transcribing";

  return (
    <div
      className="flex flex-col gap-1.5 px-4 py-3"
      style={{ borderTop: "1px solid var(--cds-border)", background: "var(--cds-surface)" }}
    >
      {voice.error && (
        <div className="text-xs" style={{ color: "#791F1F" }}>{voice.error}</div>
      )}
      <div className="flex items-end gap-2.5">
      <textarea
        ref={textareaRef}
        className="flex-1 resize-none text-sm focus:outline-none disabled:opacity-50"
        style={{
          background: "var(--cds-surface-tint)",
          border: "1px solid var(--cds-border)",
          borderRadius: 12,
          padding: "10px 14px",
          color: "var(--cds-text-primary)",
          lineHeight: 1.5,
          fontFamily: "inherit",
        }}
        rows={1}
        placeholder={recording ? "Listening…" : "Ask a question… (Shift+Enter for new line)"}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        onInput={onInput}
        disabled={loading || transcribing}
        onFocus={(e) => { (e.currentTarget as HTMLTextAreaElement).style.borderColor = "var(--cds-accent)"; (e.currentTarget as HTMLTextAreaElement).style.boxShadow = "0 0 0 3px var(--cds-accent-soft)"; }}
        onBlur={(e) => { (e.currentTarget as HTMLTextAreaElement).style.borderColor = "var(--cds-border)"; (e.currentTarget as HTMLTextAreaElement).style.boxShadow = "none"; }}
      />
      <button
        onClick={voice.toggle}
        disabled={loading || transcribing}
        title={recording ? "Stop recording" : "Speak your question"}
        className="flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition-colors"
        style={{
          background: recording ? "#F7C1C1" : "var(--cds-surface-tint)",
          animation: recording ? "pulse-mic 1.4s ease-in-out infinite" : undefined,
        }}
      >
        {transcribing ? (
          <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="var(--cds-text-muted)" strokeWidth="2">
            <path d="M21 12a9 9 0 1 1-6.219-8.56" strokeLinecap="round" />
          </svg>
        ) : (
          <svg className="w-4 h-4" fill="none" stroke={recording ? "#791F1F" : "var(--cds-text-secondary)"} viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
          </svg>
        )}
      </button>
      <button
        onClick={submit}
        disabled={loading || !text.trim()}
        className="flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition-colors"
        style={{ background: loading || !text.trim() ? "var(--cds-surface-tint-hover)" : "var(--cds-accent)" }}
      >
        {loading ? (
          <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24" stroke={loading ? "var(--cds-text-muted)" : "white"} strokeWidth="2">
            <path d="M21 12a9 9 0 1 1-6.219-8.56" strokeLinecap="round" />
          </svg>
        ) : (
          <svg className="w-4 h-4" fill="none" stroke={!text.trim() ? "var(--cds-text-muted)" : "white"} viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        )}
      </button>
      </div>
      <style>{`
        @keyframes pulse-mic {
          0%, 100% { box-shadow: 0 0 0 0 rgba(121,31,31,.35); }
          50% { box-shadow: 0 0 0 5px rgba(121,31,31,0); }
        }
      `}</style>
    </div>
  );
}
