/**
 * BIEmbed — embeds a Power BI report or Looker dashboard in an iframe.
 *
 * Props:
 *   type:      "powerbi" | "looker"
 *   embedUrl:  the secure embed URL from Power BI / Looker
 *   title:     accessible title for the iframe
 *   height:    iframe height (default "600px")
 */
interface Props {
  type: "powerbi" | "looker";
  embedUrl: string;
  title?: string;
  height?: string;
}

export function BIEmbed({ type, embedUrl, title, height = "600px" }: Props) {
  if (!embedUrl) {
    return (
      <div
        className="flex items-center justify-center rounded-xl border"
        style={{ height, background: "#f9fafb", borderColor: "#e5e7eb" }}
      >
        <span className="text-sm text-gray-400">No embed URL configured</span>
      </div>
    );
  }

  const label = title ?? (type === "powerbi" ? "Power BI Report" : "Looker Dashboard");

  return (
    <div className="rounded-xl overflow-hidden border" style={{ borderColor: "#e5e7eb" }}>
      <div
        className="flex items-center gap-2 px-4 py-2.5"
        style={{ background: "#f9fafb", borderBottom: "1px solid #e5e7eb" }}
      >
        <div
          className="w-2 h-2 rounded-full"
          style={{ background: type === "powerbi" ? "#F2C811" : "#4285F4" }}
        />
        <span className="text-xs font-medium text-gray-600">{label}</span>
      </div>
      <iframe
        src={embedUrl}
        title={label}
        width="100%"
        height={height}
        frameBorder="0"
        allowFullScreen
        style={{ display: "block" }}
      />
    </div>
  );
}
