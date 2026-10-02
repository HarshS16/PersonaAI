"use client";

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { githubApi } from "@/lib/sources";
import { oauthLoginUrl } from "@/lib/auth";
import { useJob } from "@/hooks/use-sources";

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M12 2C6.48 2 2 6.58 2 12.25c0 4.53 2.87 8.37 6.84 9.73.5.1.68-.22.68-.49 0-.24-.01-.87-.01-1.71-2.78.62-3.37-1.37-3.37-1.37-.46-1.18-1.11-1.5-1.11-1.5-.91-.64.07-.62.07-.62 1 .07 1.53 1.06 1.53 1.06.89 1.56 2.34 1.11 2.91.85.09-.66.35-1.11.63-1.37-2.22-.26-4.56-1.14-4.56-5.07 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.3.1-2.71 0 0 .84-.28 2.75 1.05A9.3 9.3 0 0 1 12 6.84c.85 0 1.71.12 2.51.34 1.91-1.33 2.75-1.05 2.75-1.05.55 1.41.2 2.45.1 2.71.64.72 1.03 1.63 1.03 2.75 0 3.94-2.34 4.81-4.57 5.06.36.32.68.94.68 1.9 0 1.37-.01 2.47-.01 2.81 0 .27.18.59.69.49A10.02 10.02 0 0 0 22 12.25C22 6.58 17.52 2 12 2z"
      />
    </svg>
  );
}

export function GitHubCard() {
  const qc = useQueryClient();
  const { data: status } = useQuery({ queryKey: ["github", "status"], queryFn: githubApi.status });
  const [username, setUsername] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const { data: job } = useJob(jobId);

  const done = job?.status === "succeeded";
  const failed = job?.status === "failed";

  useEffect(() => {
    if (done || failed) {
      qc.invalidateQueries({ queryKey: ["persona"] });
      qc.invalidateQueries({ queryKey: ["sources"] });
      qc.invalidateQueries({ queryKey: ["github"] });
    }
  }, [done, failed, qc]);

  async function connect() {
    setConnecting(true);
    setJobId(null);
    try {
      const res = await githubApi.connect(username || undefined);
      setJobId(res.job.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Connect failed");
    } finally {
      setConnecting(false);
    }
  }

  async function resync() {
    if (!status?.source_id) return;
    try {
      const job = await githubApi.sync(status.source_id);
      setJobId(job.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sync failed");
    }
  }

  const pct = Math.round((job?.progress ?? 0) * 100);
  const result = job?.result;
  const running = jobId && job && !done && !failed;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <GithubIcon className="h-4 w-4" />
          GitHub
        </CardTitle>
        <CardDescription>
          {status?.oauth_connected
            ? `Connected as ${status.username}. Sync your repositories into your persona.`
            : "Pull your public repositories, languages and READMEs into your persona."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!status?.oauth_connected && !status?.source_id && (
          <div className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="gh-username">GitHub username (public repos)</Label>
              <div className="flex gap-2">
                <Input
                  id="gh-username"
                  placeholder="e.g. octocat"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
                <Button onClick={connect} disabled={connecting || (!username && !status?.oauth_connected)}>
                  {connecting ? "Connecting…" : "Connect"}
                </Button>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              For private repos,{" "}
              <a href={oauthLoginUrl("github")} className="text-primary hover:underline">
                log in with GitHub
              </a>{" "}
              to authorize access.
            </p>
          </div>
        )}

        {(status?.oauth_connected || status?.source_id) && !running && (
          <Button variant="outline" size="sm" onClick={status?.source_id ? resync : connect}>
            <RefreshCw className="mr-2 h-4 w-4" />
            {status?.source_id ? "Re-sync repositories" : "Sync repositories"}
          </Button>
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
          <div className="flex items-center gap-2 text-sm font-medium text-green-600">
            <CheckCircle2 className="h-4 w-4" />
            Synced · {Object.values(result.created ?? {}).reduce((a, b) => a + b, 0)} facts added
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
