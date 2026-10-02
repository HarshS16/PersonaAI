"use client";

import Link from "next/link";
import { UploadCard } from "@/components/sources/upload-card";
import { GitHubCard } from "@/components/sources/github-card";
import { SourceList } from "@/components/sources/source-list";
import { ConflictsCard } from "@/components/sources/conflicts-card";

export default function SourcesPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Sources</h2>
        <p className="mt-1 text-muted-foreground">
          Connect data to build your persona. Everything extracted is linked back to its source.
        </p>
      </div>

      <ConflictsCard />
      <UploadCard />
      <GitHubCard />
      <SourceList />

      <p className="text-center text-sm text-muted-foreground">
        After ingestion, review and edit everything on your{" "}
        <Link href="/persona" className="text-primary hover:underline">
          Persona
        </Link>{" "}
        page.
      </p>
    </div>
  );
}
