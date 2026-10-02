"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Download, Globe, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { portfolioApi, type PortfolioResult } from "@/lib/portfolio";
import { ApiError } from "@/lib/api";

export default function PortfolioPage() {
  const [publicOnly, setPublicOnly] = useState(false);
  const [result, setResult] = useState<PortfolioResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    try {
      setResult(await portfolioApi.generate(publicOnly));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  }

  function download() {
    if (!result) return;
    const blob = new Blob([result.html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "portfolio.html";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Portfolio</h2>
        <p className="mt-1 text-muted-foreground">
          Generate a self-contained portfolio site from your persona — ready to host anywhere.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Generate</CardTitle>
          <CardDescription>
            Built from your skills, experience, projects, research, and achievements.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="h-4 w-4"
              checked={publicOnly}
              onChange={(e) => setPublicOnly(e.target.checked)}
            />
            Only include facts marked <span className="font-medium">public</span>
          </label>
          <div className="flex flex-wrap gap-2">
            <Button onClick={run} disabled={loading}>
              {result ? <RefreshCw className="mr-2 h-4 w-4" /> : <Globe className="mr-2 h-4 w-4" />}
              {loading ? "Generating…" : result ? "Regenerate" : "Generate portfolio"}
            </Button>
            {result && (
              <Button variant="outline" onClick={download}>
                <Download className="mr-2 h-4 w-4" />
                Download HTML
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Preview</CardTitle>
          </CardHeader>
          <CardContent>
            <iframe
              title="Portfolio preview"
              srcDoc={result.html}
              className="h-[640px] w-full rounded-md border bg-white"
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
