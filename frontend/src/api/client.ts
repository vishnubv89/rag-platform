import type { ChatMessage, ChatResponse, DocDetail, DocListResponse, IngestResponse, Org } from "../types";

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

const ADMIN_HEADERS = { "X-Admin-Key": import.meta.env.VITE_ADMIN_KEY ?? "change-me" };

export async function listOrgs(): Promise<Org[]> {
  return request<Org[]>("/admin/orgs", { headers: ADMIN_HEADERS });
}

export async function listDocs(orgId: number | null, page = 1, limit = 20): Promise<DocListResponse> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (orgId) params.set("org_id", String(orgId));
  return request<DocListResponse>(`/admin/docs?${params}`, { headers: ADMIN_HEADERS });
}

export async function searchDocs(q: string, orgId: number | null, limit = 20): Promise<DocListResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  if (orgId) params.set("org_id", String(orgId));
  return request<DocListResponse>(`/admin/docs/search?${params}`, { headers: ADMIN_HEADERS });
}

export async function getDoc(docId: number): Promise<DocDetail> {
  return request<DocDetail>(`/admin/docs/${docId}`, { headers: ADMIN_HEADERS });
}
