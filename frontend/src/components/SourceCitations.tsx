import type { SourceDoc } from "../types";

interface Props {
  sources: SourceDoc[];
  loopCount: number;
}

export function SourceCitations({ sources, loopCount }: Props) {
  if (sources.length === 0) return null;

  // Deduplicate by doc_id — one badge per document
  const seen = new Set<number>();
  const uniqueDocs = sources.filter((s) => {
    if (seen.has(s.doc_id)) return false;
    seen.add(s.doc_id);
    return true;
  });

  return (
    <details className="mt-2">
      <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600">
        {uniqueDocs.length} source{uniqueDocs.length !== 1 ? "s" : ""}
        {loopCount > 0 && (
          <span className="ml-2 text-indigo-400">
            ({loopCount} retrieval loop{loopCount !== 1 ? "s" : ""})
          </span>
        )}
      </summary>
      <div className="mt-1 flex flex-wrap gap-1">
        {uniqueDocs.map((doc) => {
          const label = doc.doc_title || `Doc #${doc.doc_id}`;
          const className = "px-2 py-0.5 bg-indigo-50 text-indigo-700 text-xs rounded-full border border-indigo-100 max-w-[220px] truncate hover:bg-indigo-100 transition-colors";
          return doc.doc_source ? (
            <a
              key={doc.doc_id}
              href={doc.doc_source}
              target="_blank"
              rel="noopener noreferrer"
              title={doc.doc_source}
              className={className}
            >
              {label}
            </a>
          ) : (
            <span key={doc.doc_id} title={label} className={className}>
              {label}
            </span>
          );
        })}
      </div>
    </details>
  );
}
