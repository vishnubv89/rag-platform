import type { ChatMessage, ChatResponse, IngestResponse, Org } from "../types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || res.statusText);
  }
  return res.json() as Promise<T>;
}

export async function sendChat(
  message: string,
  history: ChatMessage[],
  orgId: number | null,
  sessionId: string
): Promise<ChatResponse> {
  const apiHistory = history.map((m) => ({ role: m.role, content: m.content }));
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({
      message,
      history: apiHistory,
      org_id: orgId,
      session_id: sessionId,
    }),
  });
}

export async function ingestFile(file: File): Promise<IngestResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/ingest/file`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listOrgs(): Promise<Org[]> {
  return request<Org[]>("/admin/orgs", {
    headers: { "X-Admin-Key": import.meta.env.VITE_ADMIN_KEY ?? "change-me" },
  });
}
