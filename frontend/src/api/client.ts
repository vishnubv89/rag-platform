import type { ChatMessage, ChatResponse, DocDetail, DocListResponse, IngestResponse, Org } from "../types";
import { useAuthStore } from "../store/authStore";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

function authHeaders(): Record<string, string> {
  const token = useAuthStore.getState().accessToken;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...authHeaders(), ...init?.headers },
    credentials: "include",
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

export async function getAnalyticsSummary(orgId: number | null, fromDt?: string, toDt?: string) {
  const p = new URLSearchParams();
  if (orgId) p.set("org_id", String(orgId));
  if (fromDt) p.set("from_dt", fromDt);
  if (toDt) p.set("to_dt", toDt);
  return request<Record<string, number>>(`/admin/analytics/summary?${p}`, { headers: ADMIN_HEADERS });
}

export async function getAnalyticsLogs(orgId: number | null, page = 1) {
  const p = new URLSearchParams({ page: String(page), limit: "15" });
  if (orgId) p.set("org_id", String(orgId));
  return request<{ total: number; page: number; items: Record<string, unknown>[] }>(
    `/admin/analytics/logs?${p}`, { headers: ADMIN_HEADERS }
  );
}

export async function getTopSources(orgId: number | null, days = 30) {
  const p = new URLSearchParams({ days: String(days), limit: "10" });
  if (orgId) p.set("org_id", String(orgId));
  return request<{ id: number; title: string; citation_count: number }[]>(
    `/admin/analytics/top-sources?${p}`, { headers: ADMIN_HEADERS }
  );
}

export async function getTopicGraph(orgId: number | null, days = 30) {
  const p = new URLSearchParams({ days: String(days) });
  if (orgId) p.set("org_id", String(orgId));
  return request<{
    nodes: { id: number; title: string; source: string; citations: number }[];
    edges: { source: number; target: number; weight: number }[];
  }>(`/admin/analytics/topic-graph?${p}`, { headers: ADMIN_HEADERS });
}

export async function getConfig(orgId: number | null): Promise<Record<string, string>> {
  const p = new URLSearchParams();
  if (orgId) p.set("org_id", String(orgId));
  const data = await request<{ config: Record<string, string> }>(`/admin/config?${p}`, { headers: ADMIN_HEADERS });
  return data.config;
}

export async function saveConfig(orgId: number | null, settings: Record<string, string>): Promise<void> {
  await request("/admin/config", {
    method: "PUT",
    headers: ADMIN_HEADERS,
    body: JSON.stringify({ org_id: orgId, settings }),
  });
}

export async function getSuggestion(
  context: string,
  orgId: number | null,
): Promise<{ suggestion: string; sources: { doc_id: number; doc_title: string; doc_source: string }[] }> {
  return request("/suggest", {
    method: "POST",
    body: JSON.stringify({ context, org_id: orgId }),
  });
}
