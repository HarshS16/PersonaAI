import { api } from "@/lib/api";

export type Citation = { index: number; type: string; title: string };

export type ChatEvent =
  | { type: "session"; session_id: string }
  | { type: "citations"; citations: Citation[] }
  | { type: "token"; text: string }
  | { type: "error"; message: string }
  | { type: "done" };

/** Stream a chat response as Server-Sent Events. */
export async function* streamChat(
  message: string,
  sessionId: string | null,
): AsyncGenerator<ChatEvent> {
  const res = await fetch("/api/backend/chat", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.ok || !res.body) {
    throw new Error("Chat request failed");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const line = chunk.trim();
      if (line.startsWith("data: ")) {
        try {
          yield JSON.parse(line.slice(6)) as ChatEvent;
        } catch {
          // ignore malformed keepalive lines
        }
      }
    }
  }
}

export type SearchResult = {
  facts: { type: string; id: string; label: string; detail: string; confidence: number }[];
  excerpts: {
    chunk_id: string;
    text: string;
    source_title: string | null;
    source_type: string | null;
    score: number;
  }[];
};

export type ChatSessionSummary = { id: string; title: string | null; created_at: string };

export const chatApi = {
  search: (q: string) => api<SearchResult>(`/search?q=${encodeURIComponent(q)}`),
  listSessions: () => api<ChatSessionSummary[]>("/chat/sessions"),
};
