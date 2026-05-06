interface Props {
  icon: string;
  name: string;
  description: string;
  features: string[];
}

export function ComingSoon({ icon, name, description, features }: Props) {
  return (
    <div className="flex flex-col items-center justify-center h-full" style={{ background: "#fafafa" }}>
      <div
        className="w-16 h-16 rounded-2xl flex items-center justify-center text-3xl mb-6"
        style={{ background: "rgba(99,102,241,.08)", border: "1px solid rgba(99,102,241,.15)" }}
      >
        {icon}
      </div>
      <h2 className="text-xl font-bold text-gray-800 mb-2">{name}</h2>
      <p className="text-gray-500 text-sm mb-8 text-center max-w-sm">{description}</p>
      <div className="grid grid-cols-2 gap-3 max-w-md">
        {features.map((f) => (
          <div
            key={f}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm"
            style={{ background: "white", border: "1px solid #f0f0f0", color: "#374151" }}
          >
            <span className="text-indigo-400">✦</span>
            {f}
          </div>
        ))}
      </div>
      <div
        className="mt-10 px-4 py-2 rounded-full text-sm font-medium"
        style={{ background: "rgba(99,102,241,.1)", color: "#6366f1" }}
      >
        Coming in next release
      </div>
    </div>
  );
}
