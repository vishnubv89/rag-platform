export interface SourceDoc {
  chunk_id: number;
  doc_id: number;
  doc_title: string;
  doc_source: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sourceChunkIds: number[];
  sources: SourceDoc[];
  loopCount: number;
  timestamp: Date;
}

export interface Org {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
}

export interface ChatResponse {
  answer: string;
  source_chunk_ids: number[];
  sources: SourceDoc[];
  loop_count: number;
  session_id: string;
}

export type StreamEvent =
  | { type: "token"; content: string }
  | { type: "done"; answer: string; source_chunk_ids: number[]; sources: SourceDoc[]; loop_count: number; session_id: string }
  | { type: "error"; message: string };

export interface IngestResponse {
  doc_id: number;
  title: string;
  chunks: number;
}

export interface Session {
  id: string;
  preview: string;
  messages: ChatMessage[];
  orgId: number | null;
}

export interface Doc {
  id: number;
  title: string;
  source: string;
  created_at: string;
  chunk_count: number;
}

export interface DocChunk {
  id: number;
  chunk_index: number;
  text: string;
}

export interface DocDetail extends Doc {
  org_id: number;
  metadata: Record<string, unknown> | null;
  chunks: DocChunk[];
}

export interface DocListResponse {
  total: number;
  page: number;
  limit: number;
  items: Doc[];
}
