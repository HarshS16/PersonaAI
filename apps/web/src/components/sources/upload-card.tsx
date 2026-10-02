"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Upload, FileText, CheckCircle2, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { sourcesApi } from "@/lib/sources";
import { useJob } from "@/hooks/use-sources";

export function UploadCard() {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const { data: job } = useJob(jobId);

  const done = job?.status === "succeeded";
  const failed = job?.status === "failed";

  // Refresh persona + sources once the job finishes.
  useEffect(() => {
    if (done || failed) {
      qc.invalidateQueries({ queryKey: ["persona"] });
      qc.invalidateQueries({ queryKey: ["sources"] });
      qc.invalidateQueries({ queryKey: ["conflicts"] });
    }
  }, [done, failed, qc]);

  async function onFile(file: File) {
    setUploading(true);
    setJobId(null);
    try {
      const res = await sourcesApi.upload(file);
      if (res.duplicate) {
        toast.info("This document was already uploaded.");
      }
      setJobId(res.job.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  const pct = Math.round((job?.progress ?? 0) * 100);
  const result = job?.result;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Upload a resume</CardTitle>
        <CardDescription>PDF, DOCX, or TXT. We extract your skills, experience and projects — each with evidence.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onFile(f);
            e.target.value = "";
          }}
        />

        {!jobId && (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className="flex w-full flex-col items-center gap-2 rounded-lg border border-dashed p-8 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-foreground disabled:opacity-60"
          >
            <Upload className="h-6 w-6" />
            {uploading ? "Uploading…" : "Click to choose a file"}
          </button>
        )}

        {jobId && job && !done && !failed && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <FileText className="h-4 w-4 animate-pulse" />
              <span className="capitalize">{job.step ?? "processing"}…</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
            </div>
          </div>
        )}

        {done && result && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-green-600">
              <CheckCircle2 className="h-4 w-4" />
              Done
            </div>
            <ul className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
              {Object.entries(result.created ?? {}).map(([k, v]) => (
                <li key={k} className="rounded-md border p-2">
                  <span className="font-medium">{v}</span>{" "}
                  <span className="text-muted-foreground">{k} added</span>
                </li>
              ))}
            </ul>
            <p className="text-sm text-muted-foreground">
              {result.evidence_added ?? 0} evidence items ·{" "}
              {result.conflicts ? `${result.conflicts} conflict(s) to review` : "no conflicts"}
            </p>
            <Button variant="outline" size="sm" onClick={() => setJobId(null)}>
              Upload another
            </Button>
          </div>
        )}

        {failed && (
          <div className="flex items-center gap-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            {job?.error ?? "Ingestion failed"}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
