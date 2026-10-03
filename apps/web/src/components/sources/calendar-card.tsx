"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Calendar, CheckCircle2, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { sourcesApi } from "@/lib/sources";
import { useJob } from "@/hooks/use-sources";

export function CalendarCard() {
  const qc = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const { data: job } = useJob(jobId);

  const done = job?.status === "succeeded";
  const failed = job?.status === "failed";

  useEffect(() => {
    if (done || failed) {
      qc.invalidateQueries({ queryKey: ["persona"] });
      qc.invalidateQueries({ queryKey: ["sources"] });
    }
  }, [done, failed, qc]);

  async function upload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setJobId(null);
    try {
      const res = await sourcesApi.uploadCalendar(file);
      setJobId(res.job.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  const pct = Math.round((job?.progress ?? 0) * 100);
  const running = jobId && job && !done && !failed;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Calendar className="h-4 w-4" />
          Calendar Import
        </CardTitle>
        <CardDescription>
          Upload your calendar export (.ics). We extract meeting topics, professional activities, and areas of expertise.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!running && !done && (
          <div>
            <Button variant="outline" disabled={uploading} onClick={() => document.getElementById("cal-upload")?.click()}>
              {uploading ? "Uploading…" : "Choose .ics or .zip"}
            </Button>
            <input
              id="cal-upload"
              type="file"
              accept=".ics,.zip"
              className="hidden"
              onChange={upload}
            />
          </div>
        )}

        {running && (
          <div className="space-y-2">
            <div className="text-sm capitalize">{job.step ?? "processing"}…</div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
            </div>
          </div>
        )}

        {done && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium text-green-600">
              <CheckCircle2 className="h-4 w-4" />
              Calendar import complete
            </div>
            <Button variant="outline" size="sm" onClick={() => setJobId(null)}>
              Import another
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
