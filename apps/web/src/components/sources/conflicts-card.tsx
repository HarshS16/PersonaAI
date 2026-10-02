"use client";

import { toast } from "sonner";
import { AlertTriangle } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useConflicts, useResolveConflict } from "@/hooks/use-sources";

const FIELD_LABEL: Record<string, string> = {
  headline: "Professional title",
  full_name: "Full name",
  location: "Location",
  summary: "Summary",
};

export function ConflictsCard() {
  const { data: conflicts } = useConflicts();
  const resolve = useResolveConflict();

  if (!conflicts || conflicts.length === 0) return null;

  return (
    <Card className="border-amber-300 dark:border-amber-800">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <AlertTriangle className="h-4 w-4 text-amber-500" />
          Conflicts to resolve
        </CardTitle>
        <CardDescription>
          Sources disagree. Pick the correct value — nothing was changed automatically.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {conflicts.map((c) => (
          <div key={c.id} className="rounded-md border p-3">
            <p className="mb-2 text-sm font-medium">{FIELD_LABEL[c.field] ?? c.field}</p>
            <div className="flex flex-wrap gap-2">
              {c.candidates.map((cand) => (
                <Button
                  key={`${cand.source}-${cand.value}`}
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    resolve.mutate(
                      { id: c.id, value: cand.value },
                      { onSuccess: () => toast.success("Conflict resolved") },
                    )
                  }
                >
                  {cand.value}
                  <span className="ml-2 text-xs text-muted-foreground">({cand.source})</span>
                </Button>
              ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
