"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Copy, AlertTriangle, PenLine, Mail, MessageSquareText } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { contentApi, type ContentResult } from "@/lib/content";
import { ApiError } from "@/lib/api";

export default function ContentPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Content</h2>
        <p className="mt-1 text-muted-foreground">
          Generate posts, cover letters, and application answers — grounded in your real experience.
        </p>
      </div>

      <Tabs defaultValue="post">
        <TabsList>
          <TabsTrigger value="post">
            <PenLine className="mr-2 h-4 w-4" />
            Post
          </TabsTrigger>
          <TabsTrigger value="cover">
            <Mail className="mr-2 h-4 w-4" />
            Cover letter
          </TabsTrigger>
          <TabsTrigger value="answer">
            <MessageSquareText className="mr-2 h-4 w-4" />
            Application answer
          </TabsTrigger>
        </TabsList>
        <TabsContent value="post" className="mt-4">
          <PostTab />
        </TabsContent>
        <TabsContent value="cover" className="mt-4">
          <CoverTab />
        </TabsContent>
        <TabsContent value="answer" className="mt-4">
          <AnswerTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Result({ result }: { result: ContentResult }) {
  return (
    <div className="space-y-3">
      {result.warnings.length > 0 && (
        <div className="rounded-md border border-amber-300 bg-amber-500/10 p-3 text-sm dark:border-amber-800">
          <div className="mb-1 flex items-center gap-2 font-medium text-amber-600">
            <AlertTriangle className="h-4 w-4" />
            Check these before sending
          </div>
          <ul className="list-inside list-disc space-y-1 text-muted-foreground">
            {result.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-start justify-between gap-2">
            <p className="whitespace-pre-wrap text-sm">{result.content}</p>
            <Button
              size="sm"
              variant="ghost"
              className="shrink-0"
              onClick={() => {
                navigator.clipboard.writeText(result.content);
                toast.success("Copied");
              }}
            >
              <Copy className="h-4 w-4" />
            </Button>
          </div>
          {result.matched && result.matched.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1">
              {result.matched.map((m) => (
                <Badge key={m} variant="secondary" className="text-[10px]">
                  {m}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function useGen() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ContentResult | null>(null);
  async function run(fn: () => Promise<ContentResult>) {
    setLoading(true);
    try {
      setResult(await fn());
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  }
  return { loading, result, run };
}

const TONES = ["professional", "casual", "enthusiastic", "concise", "technical"];

function PostTab() {
  const [type, setType] = useState("linkedin_post");
  const [tone, setTone] = useState("professional");
  const [topic, setTopic] = useState("");
  const { loading, result, run } = useGen();

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Select value={type} onValueChange={(v) => setType(v ?? "linkedin_post")}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="linkedin_post">LinkedIn post</SelectItem>
            <SelectItem value="x_post">X / Twitter post</SelectItem>
            <SelectItem value="blog_post">Blog post</SelectItem>
            <SelectItem value="project_announcement">Project announcement</SelectItem>
            <SelectItem value="technical_article">Technical article</SelectItem>
          </SelectContent>
        </Select>
        <Select value={tone} onValueChange={(v) => setTone(v ?? "professional")}>
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TONES.map((t) => (
              <SelectItem key={t} value={t} className="capitalize">
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <Textarea
        rows={2}
        placeholder="What's it about? e.g. my RAG pipeline project"
        value={topic}
        onChange={(e) => setTopic(e.target.value)}
      />
      <Button
        onClick={() => topic.trim() && run(() => contentApi.generate(type, topic, tone))}
        disabled={loading || !topic.trim()}
      >
        {loading ? "Generating…" : "Generate"}
      </Button>
      {result && <Result result={result} />}
    </div>
  );
}

function CoverTab() {
  const [jd, setJd] = useState("");
  const [company, setCompany] = useState("");
  const [tone] = useState("professional");
  const { loading, result, run } = useGen();

  return (
    <div className="space-y-4">
      <Input placeholder="Company (optional)" value={company} onChange={(e) => setCompany(e.target.value)} />
      <Textarea
        rows={6}
        placeholder="Paste the job description…"
        value={jd}
        onChange={(e) => setJd(e.target.value)}
      />
      <Button
        onClick={() => jd.trim().length > 10 && run(() => contentApi.coverLetter(jd, company, tone))}
        disabled={loading || jd.trim().length < 10}
      >
        {loading ? "Writing…" : "Write cover letter"}
      </Button>
      {result && <Result result={result} />}
    </div>
  );
}

function AnswerTab() {
  const [question, setQuestion] = useState("");
  const [jd, setJd] = useState("");
  const { loading, result, run } = useGen();

  return (
    <div className="space-y-4">
      <Textarea
        rows={2}
        placeholder="The application question, e.g. Why do you want this role?"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
      />
      <Textarea
        rows={4}
        placeholder="Job description (optional, for context)"
        value={jd}
        onChange={(e) => setJd(e.target.value)}
      />
      <Button
        onClick={() => question.trim() && run(() => contentApi.applicationAnswer(question, jd))}
        disabled={loading || !question.trim()}
      >
        {loading ? "Answering…" : "Draft answer"}
      </Button>
      {result && <Result result={result} />}
    </div>
  );
}
