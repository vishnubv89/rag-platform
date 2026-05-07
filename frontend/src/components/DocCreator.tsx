import { useState, useRef, useCallback } from "react";
import { useChatStore } from "../store/chatStore";
import { getSuggestion } from "../api/client";

interface Source {
  doc_id: number;
  doc_title: string;
  doc_source: string;
}

function wordCount(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

function sourceLabel(url: string): string {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url || "Manual"; }
}

export function DocCreator() {
  const { activeOrg } = useChatStore();
  const orgId = activeOrg?.id ?? null;

  const [content, setContent] = useState("");
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestion, setSuggestion] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const autoResize = useCallback((el: HTMLTextAreaElement) => {
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setContent(e.target.value);
    autoResize(e.target);
    // Clear suggestion when user edits
    if (suggestion) setSuggestion(null);
  };

  const handleSuggest = async () => {
    const ctx = content.trim();
    if (!ctx) return;
    setLoading(true);
    setError(null);
    setSuggestion(null);
    setSources([]);
    try {
      const res = await getSuggestion(ctx, orgId);
      setSuggestion(res.suggestion);
      setSources(res.sources);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to get suggestion");
    } finally {
      setLoading(false);
    }
  };

  const insertSuggestion = () => {
    if (!suggestion) return;
    const separator = content.trim().endsWith("\n") ? "\n" : "\n\n";
    const newContent = content + separator + suggestion;
    setContent(newContent);
    setSuggestion(null);
    setSources([]);
    setTimeout(() => {
      if (textareaRef.current) {
        autoResize(textareaRef.current);
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(newContent.length, newContent.length);
      }
    }, 0);
  };

  const handleCopy = async () => {
    const full = title ? `# ${title}\n\n${content}` : content;
    await navigator.clipboard.writeText(full);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleClear = () => {
    setContent("");
    setTitle("");
    setSuggestion(null);
    setSources([]);
    setError(null);
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
        textareaRef.current.focus();
      }
    }, 0);
  };

  const wc = wordCount(content);

  return (
    <div className="flex h-full" style={{ background: "#fafafa" }}>
      {/* Editor panel */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Toolbar */}
        <div
          className="flex items-center gap-2 px-5 py-2.5 border-b border-gray-100"
          style={{ background: "white" }}
        >
          <span className="text-xs text-gray-400 mr-auto">
            {wc} {wc === 1 ? "word" : "words"}
          </span>

          <button
            onClick={handleSuggest}
            disabled={loading || !content.trim()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ background: "rgba(99,102,241,.1)", color: "#6366f1" }}
            onMouseEnter={(e) => { if (!loading && content.trim()) (e.currentTarget as HTMLButtonElement).style.background = "rgba(99,102,241,.18)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(99,102,241,.1)"; }}
          >
            {loading ? (
              <>
                <svg className="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
                Suggesting…
              </>
            ) : (
              <>✨ AI Suggest</>
            )}
          </button>

          <button
            onClick={handleCopy}
            disabled={!content.trim()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ background: "#f3f4f6", color: "#374151" }}
          >
            {copied ? "✓ Copied" : "Copy"}
          </button>

          <button
            onClick={handleClear}
            disabled={!content && !title}
            className="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ background: "#f3f4f6", color: "#374151" }}
          >
            Clear
          </button>
        </div>

        {/* Writing area */}
        <div className="flex-1 overflow-y-auto px-8 py-8" style={{ maxWidth: 760, margin: "0 auto", width: "100%" }}>
          <input
            type="text"
            placeholder="Document title…"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full text-2xl font-bold text-gray-900 bg-transparent border-none outline-none placeholder-gray-300 mb-4"
          />
          <div className="w-10 h-0.5 rounded mb-6" style={{ background: "rgba(99,102,241,.3)" }} />
          <textarea
            ref={textareaRef}
            placeholder="Start writing… When you want a suggestion grounded in your knowledge base, click ✨ AI Suggest."
            value={content}
            onChange={handleChange}
            className="w-full bg-transparent border-none outline-none resize-none text-gray-800 leading-relaxed text-base placeholder-gray-300"
            style={{ minHeight: 320, fontFamily: "inherit" }}
            rows={1}
          />
        </div>
      </div>

      {/* Suggestion panel */}
      {(suggestion !== null || error) && (
        <div
          className="flex flex-col border-l border-gray-100"
          style={{ width: 360, minWidth: 320, background: "white" }}
        >
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100">
            <span className="text-sm font-semibold text-gray-800">✨ Suggestion</span>
            <button
              onClick={() => { setSuggestion(null); setError(null); setSources([]); }}
              className="text-gray-400 hover:text-gray-600 text-lg leading-none"
            >
              ×
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-5 py-4">
            {error ? (
              <p className="text-sm text-red-500">{error}</p>
            ) : (
              <>
                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{suggestion}</p>

                {sources.length > 0 && (
                  <div className="mt-4">
                    <p className="text-xs text-gray-400 mb-2">Grounded in</p>
                    <div className="flex flex-wrap gap-1.5">
                      {sources.map((s) =>
                        s.doc_source ? (
                          <a
                            key={s.doc_id}
                            href={s.doc_source}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs px-2 py-0.5 rounded-full border border-indigo-100 bg-indigo-50 text-indigo-600 hover:bg-indigo-100 transition-colors"
                          >
                            {s.doc_title || sourceLabel(s.doc_source)}
                          </a>
                        ) : (
                          <span
                            key={s.doc_id}
                            className="text-xs px-2 py-0.5 rounded-full border border-gray-100 bg-gray-50 text-gray-500"
                          >
                            {s.doc_title || "Unknown"}
                          </span>
                        )
                      )}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {!error && suggestion && (
            <div className="px-5 py-4 border-t border-gray-100">
              <button
                onClick={insertSuggestion}
                className="w-full py-2 rounded-lg text-sm font-medium transition-colors"
                style={{ background: "#6366f1", color: "white" }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "#4f46e5"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "#6366f1"; }}
              >
                Insert into document
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
