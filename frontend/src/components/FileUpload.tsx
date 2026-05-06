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
          <span className="text-gray-400">
            {isDragActive ? "Drop to ingest" : "Drop a PDF, TXT or MD to ingest"}
          </span>
        )}
      </div>
    </div>
  );
}
