import { useState, useRef, useCallback, useEffect } from "react";
import { useChatStore } from "../store/chatStore";
import {
  curateDocument, type CurateResult,
  fetchSNCategories, type SNCategory,
  syncToServiceNow, type CurateSyncResult,
} from "../api/client";

function wordCount(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

function sourceLabel(url: string): string {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return url || "KB"; }
}

const DIMENSION_ICONS: Record<string, string> = {
  Structure:     "🏗️",
  Clarity:       "💡",
  Completeness:  "✅",
  Accuracy:      "🎯",
  Actionability: "⚡",
  Findability:   "🔍",
  Readability:   "📖",
};

function ScoreBadge({ score, label }: { score: number; label: string }) {
  const color =
    score >= 80 ? "#16a34a" :
    score >= 60 ? "#d97706" : "#dc2626";
  const bg =
    score >= 80 ? "rgba(22,163,74,.1)" :
    score >= 60 ? "rgba(217,119,6,.1)" : "rgba(220,38,38,.1)";
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className="text-2xl font-bold" style={{ color }}>{score}</span>
      <span className="text-xs font-semibold px-2 py-0.5 rounded-full" style={{ background: bg, color }}>
        {label}
      </span>
    </div>
  );
}

// ── ServiceNow sync panel ──────────────────────────────────────────────────
function SNSyncPanel({
  title,
  content,
  orgId,
  externalId,
}: {
  title: string;
  content: string;
  orgId: number | null;
  externalId?: string;
}) {
  const [open, setOpen]               = useState(false);
  const [categories, setCategories]   = useState<SNCategory[]>([]);
  const [catLoading, setCatLoading]   = useState(false);
  const [catError, setCatError]       = useState<string | null>(null);
  const [selectedCat, setSelectedCat] = useState("");
  const [publish, setPublish]         = useState(false);
  const [syncing, setSyncing]         = useState(false);
  const [syncResult, setSyncResult]   = useState<CurateSyncResult | null>(null);
  const [syncError, setSyncError]     = useState<string | null>(null);

  // Load categories when the panel opens
  useEffect(() => {
    if (!open || categories.length > 0) return;
    setCatLoading(true);
    setCatError(null);
    fetchSNCategories(orgId)
      .then((cats) => {
        setCategories(cats);
        if (cats.length > 0) setSelectedCat(cats[0].sys_id);
      })
      .catch((e: unknown) => {
        const msg = e instanceof Error ? e.message : "Failed to load categories";
        setCatError(msg);
      })
      .finally(() => setCatLoading(false));
  }, [open, orgId, categories.length]);

  const handleSync = async () => {
    if (!content.trim()) return;
    setSyncing(true);
    setSyncError(null);
    setSyncResult(null);
    try {
      const res = await syncToServiceNow(title, content, selectedCat, publish, orgId, externalId);
      setSyncResult(res);
    } catch (e: unknown) {
      setSyncError(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="border-t border-gray-100">
      {/* Accordion header */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-3.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
      >
        <span className="flex items-center gap-2">
          {/* ServiceNow logo-ish icon */}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
          Sync to ServiceNow
        </span>
        <svg
          width="14" height="14" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "transform .2s" }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="px-5 pb-5 flex flex-col gap-3">
          {syncResult ? (
            /* Success state */
            <div className="flex flex-col gap-2">
              <div
                className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium"
                style={{ background: "rgba(22,163,74,.1)", color: "#16a34a" }}
              >
                <span>✓</span>
                <span>Article {syncResult.action} in ServiceNow</span>
              </div>
              <a
                href={syncResult.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-indigo-600 underline underline-offset-2 break-all"
              >
                {syncResult.url}
              </a>
              <button
                onClick={() => { setSyncResult(null); setSyncError(null); }}
                className="text-xs text-gray-400 hover:text-gray-600 self-start mt-1"
              >
                Sync again
              </button>
            </div>
          ) : (
            <>
              {/* Category */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-gray-500">Category</label>
                {catLoading ? (
                  <div className="text-xs text-gray-400 py-1">Loading categories…</div>
                ) : catError ? (
                  <div className="text-xs text-red-500">{catError}</div>
                ) : (
                  <select
                    value={selectedCat}
                    onChange={(e) => setSelectedCat(e.target.value)}
                    className="w-full text-sm px-3 py-2 border border-gray-200 rounded-lg outline-none focus:border-indigo-400 bg-white text-gray-800"
                  >
                    {categories.map((c) => (
                      <option key={c.sys_id} value={c.sys_id}>{c.label}</option>
                    ))}
                    {categories.length === 0 && (
                      <option value="">(no categories found)</option>
                    )}
                  </select>
                )}
              </div>

              {/* Publish toggle */}
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-gray-500">Status</p>
                  <p className="text-xs text-gray-400">{publish ? "Will be published immediately" : "Saved as draft"}</p>
                </div>
                <button
                  onClick={() => setPublish((v) => !v)}
                  className="relative inline-flex h-5 w-9 items-center rounded-full transition-colors"
                  style={{ background: publish ? "#6366f1" : "#d1d5db" }}
                >
                  <span
                    className="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform"
                    style={{ transform: publish ? "translateX(18px)" : "translateX(2px)" }}
                  />
                </button>
              </div>

              {/* Error */}
              {syncError && (
                <p className="text-xs text-red-500">{syncError}</p>
              )}

              {/* Sync button */}
              <button
                onClick={handleSync}
                disabled={syncing || catLoading || !content.trim()}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ background: "#6366f1", color: "white" }}
                onMouseEnter={(e) => { if (!syncing) (e.currentTarget as HTMLButtonElement).style.background = "#4f46e5"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "#6366f1"; }}
              >
                {syncing ? (
                  <>
                    <svg className="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                    </svg>
                    Syncing…
                  </>
                ) : (
                  <>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="17 1 21 5 17 9" />
                      <path d="M3 11V9a4 4 0 0 1 4-4h14" />
                      <polyline points="7 23 3 19 7 15" />
                      <path d="M21 13v2a4 4 0 0 1-4 4H3" />
                    </svg>
                    {externalId ? "Update in ServiceNow" : "Create in ServiceNow"}
                  </>
                )}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────
export function DocCurator() {
  const { activeOrg } = useChatStore();
  const orgId = activeOrg?.id ?? null;

  const [title, setTitle]       = useState("");
  const [content, setContent]   = useState("");
  const [loading, setLoading]   = useState(false);
  const [result, setResult]     = useState<CurateResult | null>(null);
  const [error, setError]       = useState<string | null>(null);
  const [copied, setCopied]     = useState(false);
  const [applied, setApplied]   = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Track the SN external_id of the doc in the editor (set after sync or if doc came from SN)
  const [externalId, setExternalId] = useState<string | undefined>(undefined);

  const autoResize = useCallback((el: HTMLTextAreaElement) => {
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setContent(e.target.value);
    autoResize(e.target);
    if (result) { setResult(null); setApplied(false); }
  };

  const handleCurate = async () => {
    const ctx = content.trim();
    if (!ctx) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setApplied(false);
    try {
      const res = await curateDocument(title.trim(), ctx, orgId);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Curation failed");
    } finally {
      setLoading(false);
    }
  };

  const handleApply = () => {
    if (!result) return;
    if (result.improved_title) setTitle(result.improved_title);
    setContent(result.improved_content);
    setApplied(true);
    setTimeout(() => {
      if (textareaRef.current) {
        autoResize(textareaRef.current);
        textareaRef.current.focus();
      }
    }, 0);
  };

  const handleCopy = async () => {
    const src =
      applied || !result
        ? (title ? `# ${title}\n\n${content}` : content)
        : (result.improved_title
            ? `# ${result.improved_title}\n\n${result.improved_content}`
            : result.improved_content);
    await navigator.clipboard.writeText(src);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleClear = () => {
    setTitle(""); setContent(""); setResult(null); setError(null);
    setApplied(false); setExternalId(undefined);
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
        textareaRef.current.focus();
      }
    }, 0);
  };

  const wc = wordCount(content);
  const hasContent = !!content.trim();

  // After applying, the sync panel should use the improved content
  const syncTitle   = applied && result ? result.improved_title || title : title;
  const syncContent = applied && result ? result.improved_content : content;

  return (
    <div className="flex h-full" style={{ background: "#fafafa" }}>
      {/* ── Editor panel ── */}
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
            onClick={handleCurate}
            disabled={loading || !hasContent}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ background: "rgba(99,102,241,.1)", color: "#6366f1" }}
            onMouseEnter={(e) => { if (!loading && hasContent) (e.currentTarget as HTMLButtonElement).style.background = "rgba(99,102,241,.18)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(99,102,241,.1)"; }}
          >
            {loading ? (
              <>
                <svg className="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
                Curating…
              </>
            ) : (
              <>✨ Curate Document</>
            )}
          </button>

          <button
            onClick={handleCopy}
            disabled={!hasContent && !result}
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
        <div
          className="flex-1 overflow-y-auto px-8 py-8"
          style={{ maxWidth: 760, margin: "0 auto", width: "100%" }}
        >
          {!hasContent && !loading && (
            <div
              className="mb-6 px-4 py-3 rounded-xl text-sm text-indigo-700 flex items-start gap-2"
              style={{ background: "rgba(99,102,241,.07)" }}
            >
              <span className="mt-0.5">💡</span>
              <span>
                Paste or write your knowledge article, SOP, FAQ, or troubleshooting guide.
                Click <strong>✨ Curate Document</strong> to improve it against{" "}
                <strong>KCS v6 &amp; ITIL 4</strong> quality standards, then sync back to ServiceNow.
              </span>
            </div>
          )}

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
            placeholder="Paste or write your document here…"
            value={content}
            onChange={handleChange}
            className="w-full bg-transparent border-none outline-none resize-none text-gray-800 leading-relaxed text-base placeholder-gray-300"
            style={{ minHeight: 320, fontFamily: "inherit" }}
            rows={1}
          />
        </div>
      </div>

      {/* ── Quality report + sync panel ── */}
      {(result !== null || error || hasContent) && (
        <div
          className="flex flex-col border-l border-gray-100"
          style={{ width: 380, minWidth: 340, background: "white" }}
        >
          {/* Panel header */}
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100">
            <span className="text-sm font-semibold text-gray-800">
              {result ? "✨ Quality Report" : "✨ Doc Curator"}
            </span>
            {result && (
              <button
                onClick={() => { setResult(null); setError(null); setApplied(false); }}
                className="text-gray-400 hover:text-gray-600 text-lg leading-none"
              >
                ×
              </button>
            )}
          </div>

          <div className="flex-1 overflow-y-auto">
            {/* Waiting state — no result yet */}
            {!result && !error && hasContent && (
              <div className="px-5 py-6 text-center">
                <p className="text-sm text-gray-400 mb-1">Ready to curate</p>
                <p className="text-xs text-gray-300">Click ✨ Curate Document to get a quality report and sync options</p>
              </div>
            )}

            {error && (
              <div className="px-5 py-4">
                <p className="text-sm text-red-500">{error}</p>
              </div>
            )}

            {result && (
              <>
                {/* Score row */}
                <div className="flex items-center justify-around px-5 py-4 border-b border-gray-50">
                  <ScoreBadge score={result.score_before} label="Before" />
                  <div className="flex flex-col items-center gap-1">
                    <svg width="28" height="14" viewBox="0 0 28 14" fill="none">
                      <path d="M2 7h24M18 2l6 5-6 5" stroke="#6366f1" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    <span className="text-xs text-indigo-500 font-semibold">
                      +{result.score_after - result.score_before}
                    </span>
                  </div>
                  <ScoreBadge score={result.score_after} label="After" />
                </div>

                {/* Improved title */}
                {result.improved_title && result.improved_title !== title && (
                  <div className="px-5 py-3 border-b border-gray-50">
                    <p className="text-xs text-gray-400 mb-1">Improved title</p>
                    <p className="text-sm font-semibold text-gray-800">{result.improved_title}</p>
                  </div>
                )}

                {/* Changes list */}
                {result.changes.length > 0 && (
                  <div className="px-5 py-3 border-b border-gray-50">
                    <p className="text-xs text-gray-400 mb-2.5">Improvements made</p>
                    <div className="flex flex-col gap-2.5">
                      {result.changes.map((c, i) => (
                        <div key={i} className="flex gap-2 text-sm">
                          <span className="shrink-0 text-base leading-snug">{DIMENSION_ICONS[c.dimension] ?? "•"}</span>
                          <div>
                            <span className="font-semibold text-gray-700">{c.dimension}</span>
                            <span className="text-gray-500"> — {c.description}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* KB sources */}
                {result.sources.length > 0 && (
                  <div className="px-5 py-3 border-b border-gray-50">
                    <p className="text-xs text-gray-400 mb-2">Grounded in</p>
                    <div className="flex flex-wrap gap-1.5">
                      {result.sources.map((s) =>
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
                            {s.doc_title || "KB Article"}
                          </span>
                        )
                      )}
                    </div>
                  </div>
                )}

                {/* Improved content preview */}
                <div className="px-5 py-3 border-b border-gray-50">
                  <p className="text-xs text-gray-400 mb-2">Improved document preview</p>
                  <div
                    className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap rounded-lg p-3"
                    style={{ background: "#f8faff", maxHeight: 220, overflowY: "auto" }}
                  >
                    {result.improved_content}
                  </div>
                </div>

                {/* Apply button */}
                <div className="px-5 py-4 border-b border-gray-100 flex flex-col gap-2">
                  {applied ? (
                    <div
                      className="w-full py-2 rounded-lg text-sm font-medium text-center"
                      style={{ background: "rgba(22,163,74,.1)", color: "#16a34a" }}
                    >
                      ✓ Improvements applied to editor
                    </div>
                  ) : (
                    <button
                      onClick={handleApply}
                      className="w-full py-2 rounded-lg text-sm font-medium transition-colors"
                      style={{ background: "#6366f1", color: "white" }}
                      onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "#4f46e5"; }}
                      onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "#6366f1"; }}
                    >
                      Apply improvements
                    </button>
                  )}
                </div>
              </>
            )}
          </div>

          {/* ── ServiceNow sync accordion — always visible when content exists ── */}
          {hasContent && (
            <SNSyncPanel
              title={syncTitle}
              content={syncContent}
              orgId={orgId}
              externalId={externalId}
            />
          )}
        </div>
      )}
    </div>
  );
}
