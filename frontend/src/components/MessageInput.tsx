import { useState, useRef, type KeyboardEvent } from "react";

interface Props {
  onSend: (text: string) => void;
  loading: boolean;
}

export function MessageInput({ onSend, loading }: Props) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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

  return (
    <div
      className="flex items-end gap-2.5 px-4 py-3"
      style={{ borderTop: "1px solid var(--cds-border)", background: "var(--cds-surface)" }}
    >
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
        placeholder="Ask a question… (Shift+Enter for new line)"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        onInput={onInput}
        disabled={loading}
        onFocus={(e) => { (e.currentTarget as HTMLTextAreaElement).style.borderColor = "var(--cds-accent)"; (e.currentTarget as HTMLTextAreaElement).style.boxShadow = "0 0 0 3px var(--cds-accent-soft)"; }}
        onBlur={(e) => { (e.currentTarget as HTMLTextAreaElement).style.borderColor = "var(--cds-border)"; (e.currentTarget as HTMLTextAreaElement).style.boxShadow = "none"; }}
      />
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
  );
}
