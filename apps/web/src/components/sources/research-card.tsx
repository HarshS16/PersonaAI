"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BookOpen, CheckCircle2, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { researchApi } from "@/lib/sources";
import { useJob } from "@/hooks/use-sources";

const PROVIDERS = [
  { value: "semantic_scholar", label: "Semantic Scholar" },
  { value: "arxiv", label: "arXiv" },
  { value: "orcid", label: "ORCID" },
];

export function ResearchCard() {
  const qc = useQueryClient();
  const [provider, setProvider] = useState("semantic_scholar");
  const [query, setQuery] = useState("");
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
      const res = await researchApi.connect(provider, query);
      setJobId(res.job.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Connect failed");
    } finally {
      setConnecting(false);
    }
  }

  const placeholder =
    provider === "orcid"
      ? "e.g. 0000-0002-1825-0097"
      : "e.g. Geoffrey Hinton";

  const pct = Math.round((job?.progress ?? 0) * 100);
  const result = job?.result;
  const running = jobId && job && !done && !failed;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <BookOpen className="h-4 w-4" />
          Research / Publications
        </CardTitle>
        <CardDescription>
          Import your academic publications from Semantic Scholar, arXiv, or ORCID.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!running && !done && (
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>Provider</Label>
              <Select value={provider} onValueChange={(v) => setProvider(v ?? "semantic_scholar")}>
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
              <Label htmlFor="research-query">
                {provider === "orcid" ? "ORCID ID" : "Author name"}
              </Label>
              <div className="flex gap-2">
                <Input
                  id="research-query"
                  placeholder={placeholder}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <Button onClick={connect} disabled={connecting || !query}>
                  {connecting ? "Importing…" : "Import"}
                </Button>
              </div>
            </div>
          </div>
        )}

        {running && (
          <div className="space-y-2">
            <div className="text-sm capitalize">{job.step ?? "fetching"}…</div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
            </div>
          </div>
        )}

        {done && result && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium text-green-600">
              <CheckCircle2 className="h-4 w-4" />
              Imported · {(result as Record<string, unknown>).papers as number ?? 0} publications found
            </div>
            <Button variant="outline" size="sm" onClick={() => { setJobId(null); setQuery(""); }}>
              Import from another source
            </Button>
          </div>
        )}

        {failed && (
          <div className="flex items-center gap-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            {job?.error ?? "Import failed"}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
