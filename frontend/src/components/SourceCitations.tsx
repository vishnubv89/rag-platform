interface Props {
  chunkIds: number[];
  loopCount: number;
}

export function SourceCitations({ chunkIds, loopCount }: Props) {
  if (chunkIds.length === 0) return null;
  return (
    <details className="mt-2">
      <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600">
        {chunkIds.length} source{chunkIds.length !== 1 ? "s" : ""}
        {loopCount > 0 && <span className="ml-2 text-indigo-400">({loopCount} retrieval loop{loopCount !== 1 ? "s" : ""})</span>}
      </summary>
      <div className="mt-1 flex flex-wrap gap-1">
        {chunkIds.map((id) => (
          <span key={id} className="px-2 py-0.5 bg-indigo-50 text-indigo-700 text-xs rounded-full border border-indigo-100">
            chunk #{id}
          </span>
        ))}
      </div>
    </details>
  );
}
