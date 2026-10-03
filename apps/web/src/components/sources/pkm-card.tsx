"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Bookmark, FileText, CheckCircle2, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { sourcesApi } from "@/lib/sources";
import { useJob } from "@/hooks/use-sources";

export function PKMCard() {
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

  async function uploadBookmarks(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setJobId(null);
    try {
      const res = await sourcesApi.uploadBookmarks(file);
      setJobId(res.job.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function uploadNotes(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setJobId(null);
    try {
      const res = await sourcesApi.uploadNotes(file);
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
          <Bookmark className="h-4 w-4" />
          Knowledge Management
        </CardTitle>
        <CardDescription>
          Import your bookmarks or markdown notes. We extract interests, learning areas, and knowledge domains.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!running && !done && (
          <Tabs defaultValue="bookmarks">
            <TabsList className="mb-3">
              <TabsTrigger value="bookmarks">
                <Bookmark className="mr-1 h-3 w-3" />
                Bookmarks
              </TabsTrigger>
              <TabsTrigger value="notes">
                <FileText className="mr-1 h-3 w-3" />
                Notes
              </TabsTrigger>
            </TabsList>
            <TabsContent value="bookmarks">
              <p className="mb-2 text-sm text-muted-foreground">
                Export bookmarks from your browser as HTML and upload here.
              </p>
              <Button variant="outline" disabled={uploading} onClick={() => document.getElementById("bm-upload")?.click()}>
                {uploading ? "Uploading…" : "Choose bookmarks.html"}
              </Button>
              <input
                id="bm-upload"
                type="file"
                accept=".html,.htm"
                className="hidden"
                onChange={uploadBookmarks}
              />
            </TabsContent>
            <TabsContent value="notes">
              <p className="mb-2 text-sm text-muted-foreground">
                Upload markdown notes (.md) or a ZIP of markdown files.
              </p>
              <Button variant="outline" disabled={uploading} onClick={() => document.getElementById("notes-upload")?.click()}>
                {uploading ? "Uploading…" : "Choose .md or .zip"}
              </Button>
              <input
                id="notes-upload"
                type="file"
                accept=".md,.zip"
                className="hidden"
                onChange={uploadNotes}
              />
            </TabsContent>
          </Tabs>
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
              Import complete
            </div>
            <Button variant="outline" size="sm" onClick={() => setJobId(null)}>
              Import more
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
