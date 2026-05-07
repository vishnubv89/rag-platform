import type { SourceDoc } from "../types";

interface Props {
  sources: SourceDoc[];
  loopCount: number;
}

export function SourceCitations({ sources, loopCount }: Props) {
  if (sources.length === 0) return null;

  const seen = new Set<number>();
  const uniqueDocs = sources.filter((s) => {
    if (seen.has(s.doc_id)) return false;
    seen.add(s.doc_id);
    return true;
  });

  return (
    <details className="mt-2">
      <summary
        className="text-xs cursor-pointer select-none"
        style={{ color: "#9ca3af" }}
      >
        {uniqueDocs.length} source{uniqueDocs.length !== 1 ? "s" : ""}
        {loopCount > 0 && (
          <span className="ml-2" style={{ color: "#bfdbfe" }}>
            {loopCount} retrieval loop{loopCount !== 1 ? "s" : ""}
          </span>
        )}
      </summary>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {uniqueDocs.map((doc) => {
          const label = doc.doc_title || `Doc #${doc.doc_id}`;
          const baseStyle: React.CSSProperties = {
            fontSize: "0.7rem",
            padding: "3px 8px",
            borderRadius: 6,
            border: "1px solid #e8e8ea",
            background: "#f7f7f8",
            color: "#4b5563",
            maxWidth: 200,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            display: "inline-block",
            textDecoration: "none",
          };
          return doc.doc_source ? (
            <a
              key={doc.doc_id}
              href={doc.doc_source}
              target="_blank"
              rel="noopener noreferrer"
              title={doc.doc_source}
              style={{ ...baseStyle, color: "#2563eb", background: "#eff6ff", borderColor: "#bfdbfe" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLAnchorElement).style.background = "#dbeafe"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLAnchorElement).style.background = "#eff6ff"; }}
            >
              {label}
            </a>
          ) : (
            <span key={doc.doc_id} title={label} style={baseStyle}>{label}</span>
          );
        })}
      </div>
    </details>
  );
}
