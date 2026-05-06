export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sourceChunkIds: number[];
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
  loop_count: number;
  session_id: string;
}

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
