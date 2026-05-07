interface Props {
  name: string;
  description: string;
  features: string[];
}

export function ComingSoon({ name, description, features }: Props) {
  return (
    <div className="flex flex-col items-center justify-center h-full" style={{ background: "#f7f7f8" }}>
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center mb-5"
        style={{ background: "#ffffff", border: "1px solid #e8e8ea" }}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h2 className="text-base font-semibold text-gray-800 mb-1.5">{name}</h2>
      <p className="text-sm text-gray-400 mb-8 text-center max-w-xs leading-relaxed">{description}</p>
      <div className="grid grid-cols-2 gap-2 max-w-sm">
        {features.map((f) => (
          <div
            key={f}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-gray-500"
            style={{ background: "#ffffff", border: "1px solid #e8e8ea" }}
          >
            <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ background: "#d1d5db" }} />
            {f}
          </div>
        ))}
      </div>
      <p className="mt-8 text-xs text-gray-400">Coming in a future release</p>
    </div>
  );
}
