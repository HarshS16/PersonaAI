"use client";

import { useRef, useState } from "react";
import { Send, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { streamChat, type Citation } from "@/lib/chat";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
};

const SUGGESTED = [
  "What are my strongest skills?",
  "Find my projects involving AI.",
  "What experience demonstrates backend development?",
  "What should I learn next?",
];

export default function AskPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const sessionId = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  function scrollToBottom() {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
  }

  async function send(text: string) {
    const question = text.trim();
    if (!question || streaming) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: question }, { role: "assistant", content: "" }]);
    setStreaming(true);
    scrollToBottom();

    try {
      for await (const evt of streamChat(question, sessionId.current)) {
        if (evt.type === "session") {
          sessionId.current = evt.session_id;
        } else if (evt.type === "citations") {
          setMessages((m) => {
            const next = [...m];
            next[next.length - 1] = { ...next[next.length - 1], citations: evt.citations };
            return next;
          });
        } else if (evt.type === "token") {
          setMessages((m) => {
            const next = [...m];
            const last = next[next.length - 1];
            next[next.length - 1] = { ...last, content: last.content + evt.text };
            return next;
          });
          scrollToBottom();
        } else if (evt.type === "error") {
          toast.error(evt.message);
        }
      }
    } catch {
      toast.error("Chat failed. Is the API running?");
    } finally {
      setStreaming(false);
      scrollToBottom();
    }
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-3xl flex-col">
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto pb-4">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-6 text-center">
            <div className="flex items-center gap-2 text-lg font-medium">
              <Sparkles className="h-5 w-5 text-primary" />
              Ask anything about your professional identity
            </div>
            <div className="grid w-full max-w-md gap-2">
              {SUGGESTED.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-md border px-4 py-2 text-left text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m, i) => <MessageBubble key={i} message={m} streaming={streaming && i === messages.length - 1} />)
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex items-center gap-2 border-t pt-4"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask anything about your professional identity…"
          className="flex-1 rounded-md border bg-background px-4 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          disabled={streaming}
        />
        <Button type="submit" size="icon" disabled={streaming || !input.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}

function MessageBubble({ message, streaming }: { message: ChatMessage; streaming: boolean }) {
  const isUser = message.role === "user";
  return (
    <div className={isUser ? "flex justify-end" : "flex justify-start"}>
      <div
        className={
          isUser
            ? "max-w-[80%] rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground"
            : "max-w-[85%] space-y-2 rounded-lg bg-muted px-4 py-2 text-sm"
        }
      >
        <p className="whitespace-pre-wrap">
          {message.content || (streaming ? "…" : "")}
        </p>
        {message.citations && message.citations.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {message.citations.map((c) => (
              <Badge key={c.index} variant="secondary" className="text-[10px]">
                [{c.index}] {c.title}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
