"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Rss, CheckCircle2, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { blogApi } from "@/lib/sources";
import { useJob } from "@/hooks/use-sources";

const PROVIDERS = [
  { value: "medium", label: "Medium" },
  { value: "hashnode", label: "Hashnode" },
  { value: "devto", label: "Dev.to" },
  { value: "rss", label: "RSS feed URL" },
];

export function BlogCard() {
  const qc = useQueryClient();
  const [provider, setProvider] = useState("medium");
  const [handle, setHandle] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const { data: job } = useJob(jobId);

  const done = job?.status === "succeeded";
  const failed = job?.status === "failed";

  useEffect(() => {
    if (done || failed) {
      qc.invalidateQueries({ queryKey: ["persona"] });
      qc.invalidateQueries({ queryKey: ["sources"] });
    }
  }, [done, failed, qc]);

  async function connect() {
    setConnecting(true);
    setJobId(null);
    try {
      const res = await blogApi.connect(provider, handle);
      setJobId(res.job.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Connect failed");
    } finally {
      setConnecting(false);
    }
  }

  const pct = Math.round((job?.progress ?? 0) * 100);
  const result = job?.result;
  const running = jobId && job && !done && !failed;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Rss className="h-4 w-4" />
          Blog / RSS
        </CardTitle>
        <CardDescription>
          Import your blog articles. We extract skills you write about, build search indexes, and learn your writing style.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!running && !done && (
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>Platform</Label>
              <Select value={provider} onValueChange={(v) => setProvider(v ?? "medium")}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PROVIDERS.map((p) => (
                    <SelectItem key={p.value} value={p.value}>
                      {p.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="blog-handle">
                {provider === "rss" ? "Feed URL" : "Username / handle"}
              </Label>
              <div className="flex gap-2">
                <Input
                  id="blog-handle"
                  placeholder={provider === "rss" ? "https://example.com/feed.xml" : "e.g. johndoe"}
                  value={handle}
                  onChange={(e) => setHandle(e.target.value)}
                />
                <Button onClick={connect} disabled={connecting || !handle}>
                  {connecting ? "Connecting…" : "Connect"}
                </Button>
              </div>
            </div>
          </div>
        )}

        {running && (
          <div className="space-y-2">
            <div className="text-sm capitalize">{job.step ?? "working"}…</div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
            </div>
          </div>
        )}

        {done && result && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium text-green-600">
              <CheckCircle2 className="h-4 w-4" />
              Synced · {(result as Record<string, unknown>).articles as number ?? 0} articles indexed
            </div>
            <Button variant="outline" size="sm" onClick={() => { setJobId(null); setHandle(""); }}>
              Add another
            </Button>
          </div>
        )}

        {failed && (
          <div className="flex items-center gap-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            {job?.error ?? "Sync failed"}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
