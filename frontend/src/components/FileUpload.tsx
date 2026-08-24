import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { ingestFile } from "../api/client";

export function FileUpload() {
  const [status, setStatus] = useState<"idle" | "uploading" | "done" | "error">("idle");
  const [result, setResult] = useState<string>("");

  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    if (!file) return;
    setStatus("uploading");
    try {
      const res = await ingestFile(file);
      setResult(`"${res.title}" ingested — ${res.chunks} chunks`);
      setStatus("done");
    } catch (e) {
      setResult(e instanceof Error ? e.message : "Upload failed");
      setStatus("error");
    }
    setTimeout(() => setStatus("idle"), 4000);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"], "text/plain": [".txt"], "text/markdown": [".md"] },
    multiple: false,
  });

  return (
    <div className="p-4" style={{ borderTop: "1px solid var(--cds-border)", background: "var(--cds-surface-tint)" }}>
      <div
        {...getRootProps()}
        className="border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-colors text-sm"
        style={{
          borderColor: isDragActive ? "#F0997B" : "var(--cds-border)",
          background: isDragActive ? "var(--cds-accent-tint)" : "transparent",
        }}
      >
        <input {...getInputProps()} />
        {status === "uploading" && <span style={{ color: "var(--cds-accent)" }}>Uploading…</span>}
        {status === "done" && <span className="text-green-600">{result}</span>}
        {status === "error" && <span className="text-red-500">{result}</span>}
        {status === "idle" && (
          <div className="flex flex-col items-center gap-2">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--cds-text-muted)" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            {isDragActive ? (
              <span className="text-sm font-medium" style={{ color: "var(--cds-accent)" }}>Drop to ingest</span>
            ) : (
              <>
                <span className="text-xs" style={{ color: "var(--cds-text-muted)" }}>PDF, TXT or MD · drag here or</span>
                <span className="text-xs font-medium px-3 py-1 rounded-lg" style={{ background: "var(--cds-accent-tint)", color: "var(--cds-accent-text)" }}>
                  Browse files
                </span>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
