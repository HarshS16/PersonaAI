"use client";

import { useState } from "react";
import { toast } from "sonner";
import { FileText, Target, MessagesSquare, Copy, ShieldCheck } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { careerApi, type JDResult, type ResumeResult, type InterviewResult } from "@/lib/career";
import { ApiError } from "@/lib/api";

export default function CareerPage() {
  const [jd, setJd] = useState("");

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Career</h2>
        <p className="mt-1 text-muted-foreground">
          Analyze a job description, generate an evidence-backed resume, and prepare for interviews.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Job description</CardTitle>
          <CardDescription>Paste a JD to tailor everything below to it.</CardDescription>
        </CardHeader>
        <CardContent>
          <Textarea
            rows={6}
            placeholder="Paste the job description here…"
            value={jd}
            onChange={(e) => setJd(e.target.value)}
          />
        </CardContent>
      </Card>

      <Tabs defaultValue="gap">
        <TabsList>
          <TabsTrigger value="gap">
            <Target className="mr-2 h-4 w-4" />
            Gap analysis
          </TabsTrigger>
          <TabsTrigger value="resume">
            <FileText className="mr-2 h-4 w-4" />
            Resume
          </TabsTrigger>
          <TabsTrigger value="interview">
            <MessagesSquare className="mr-2 h-4 w-4" />
            Interview
          </TabsTrigger>
        </TabsList>
        <TabsContent value="gap" className="mt-4">
          <GapTab jd={jd} />
        </TabsContent>
        <TabsContent value="resume" className="mt-4">
          <ResumeTab jd={jd} />
        </TabsContent>
        <TabsContent value="interview" className="mt-4">
          <InterviewTab jd={jd} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function needJd(jd: string): boolean {
  if (jd.trim().length < 10) {
    toast.error("Paste a job description first.");
    return true;
  }
  return false;
}

const STATUS_STYLE: Record<string, string> = {
  strong: "bg-green-500/15 text-green-600 border-green-500/30",
  partial: "bg-amber-500/15 text-amber-600 border-amber-500/30",
  none: "bg-destructive/15 text-destructive border-destructive/30",
};

function GapTab({ jd }: { jd: string }) {
  const [result, setResult] = useState<JDResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    if (needJd(jd)) return;
    setLoading(true);
    try {
      setResult(await careerApi.analyzeJd(jd));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <Button onClick={run} disabled={loading}>
        {loading ? "Analyzing…" : "Analyze requirements"}
      </Button>
      {result && (
        <div className="space-y-2">
          {result.matches.map((m) => (
            <div key={m.requirement} className="rounded-md border p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium capitalize">{m.requirement}</span>
                <Badge variant="outline" className={STATUS_STYLE[m.status]}>
                  {m.status === "none" ? "not demonstrated" : m.status}
                </Badge>
              </div>
              {m.evidence.length > 0 && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Evidence: {m.evidence[0]}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ResumeTab({ jd }: { jd: string }) {
  const [role, setRole] = useState("");
  const [result, setResult] = useState<ResumeResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    if (needJd(jd)) return;
    setLoading(true);
    try {
      setResult(await careerApi.generateResume(jd, role));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input placeholder="Target role (optional)" value={role} onChange={(e) => setRole(e.target.value)} />
        <Button onClick={run} disabled={loading}>
          {loading ? "Generating…" : "Generate resume"}
        </Button>
      </div>

      {result && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3 rounded-md border p-3 text-sm">
            <span className="font-medium">ATS keyword coverage:</span>
            <Badge variant="secondary">{Math.round(result.ats.keyword_coverage * 100)}%</Badge>
            {result.missing_requirements.length > 0 && (
              <span className="text-muted-foreground">
                Missing: {result.missing_requirements.join(", ")}
              </span>
            )}
            <Button
              size="sm"
              variant="outline"
              className="ml-auto"
              onClick={() => {
                navigator.clipboard.writeText(result.markdown);
                toast.success("Resume markdown copied");
              }}
            >
              <Copy className="mr-2 h-4 w-4" />
              Copy markdown
            </Button>
          </div>

          <Card>
            <CardContent className="space-y-4 pt-6">
              <div>
                <h3 className="text-lg font-semibold">{result.resume.name ?? "Your Resume"}</h3>
                <p className="text-sm text-muted-foreground">{result.resume.headline}</p>
                <p className="mt-2 text-sm">{result.resume.summary}</p>
              </div>

              <section>
                <h4 className="mb-1 text-sm font-semibold">Skills</h4>
                <div className="flex flex-wrap gap-1">
                  {result.resume.skills.map((s) => (
                    <Badge key={s} variant="secondary">{s}</Badge>
                  ))}
                </div>
              </section>

              {result.resume.experience.length > 0 && (
                <section>
                  <h4 className="mb-2 text-sm font-semibold">Experience</h4>
                  <div className="space-y-3">
                    {result.resume.experience.map((e, i) => (
                      <div key={i}>
                        <p className="text-sm font-medium">
                          {e.role}
                          {e.company ? ` · ${e.company}` : ""}
                        </p>
                        <ul className="mt-1 space-y-1">
                          {e.bullets.map((b, j) => (
                            <li key={j} className="flex items-start gap-1 text-sm text-muted-foreground">
                              <ShieldCheck className="mt-0.5 h-3 w-3 shrink-0 text-green-600" />
                              <span>
                                {b.text}
                                {b.softened && (
                                  <Badge variant="outline" className="ml-1 text-[10px]">softened</Badge>
                                )}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {result.resume.projects.length > 0 && (
                <section>
                  <h4 className="mb-2 text-sm font-semibold">Projects</h4>
                  <div className="space-y-3">
                    {result.resume.projects.map((p, i) => (
                      <div key={i}>
                        <p className="text-sm font-medium">{p.name}</p>
                        <ul className="mt-1 space-y-1">
                          {p.bullets.map((b, j) => (
                            <li key={j} className="text-sm text-muted-foreground">• {b.text}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </CardContent>
          </Card>
          <p className="text-xs text-muted-foreground">
            Every bullet is checked against your evidence; unsupported claims are dropped and
            over-claimed leadership is softened.
          </p>
        </div>
      )}
    </div>
  );
}

function InterviewTab({ jd }: { jd: string }) {
  const [mode, setMode] = useState("technical");
  const [result, setResult] = useState<InterviewResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    try {
      setResult(await careerApi.startInterview(mode, jd));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Select value={mode} onValueChange={(v) => setMode(v ?? "technical")}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="technical">Technical</SelectItem>
            <SelectItem value="project">Project</SelectItem>
            <SelectItem value="system_design">System design</SelectItem>
            <SelectItem value="behavioral">Behavioral</SelectItem>
            <SelectItem value="hr">HR</SelectItem>
          </SelectContent>
        </Select>
        <Button onClick={run} disabled={loading}>
          {loading ? "Preparing…" : "Generate questions"}
        </Button>
      </div>

      {result && (
        <ol className="space-y-2">
          {result.questions.map((q, i) => (
            <li key={i} className="rounded-md border p-3 text-sm">
              <span className="mr-2 font-medium text-muted-foreground">{i + 1}.</span>
              {q.question}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
