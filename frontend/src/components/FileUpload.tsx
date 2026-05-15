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
    <div className="p-4 border-t border-gray-100 bg-gray-50">
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-colors text-sm ${
          isDragActive ? "border-indigo-400 bg-indigo-50" : "border-gray-200 hover:border-indigo-300"
        }`}
      >
        <input {...getInputProps()} />
        {status === "uploading" && <span className="text-indigo-500">Uploading…</span>}
        {status === "done" && <span className="text-green-600">{result}</span>}
        {status === "error" && <span className="text-red-500">{result}</span>}
        {status === "idle" && (
          <div className="flex flex-col items-center gap-2">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            {isDragActive ? (
              <span className="text-indigo-500 text-sm font-medium">Drop to ingest</span>
            ) : (
              <>
                <span className="text-gray-400 text-xs">PDF, TXT or MD · drag here or</span>
                <span className="text-xs font-medium px-3 py-1 rounded-lg" style={{ background: "#eff6ff", color: "#2563eb" }}>
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
