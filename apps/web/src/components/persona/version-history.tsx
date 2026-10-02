"use client";

import { toast } from "sonner";
import { History, RotateCcw } from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { usePersonaVersions, useRestoreVersion } from "@/hooks/use-persona";

export function VersionHistory() {
  const { data, isLoading, refetch } = usePersonaVersions();
  const restore = useRestoreVersion();

  return (
    <Popover onOpenChange={(o) => o && refetch()}>
      <PopoverTrigger render={<Button variant="outline" size="sm" />}>
        <History className="mr-2 h-4 w-4" />
        History
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80">
        <p className="mb-2 text-sm font-medium">Version history</p>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : !data || data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No snapshots yet. They are created automatically as you edit.
          </p>
        ) : (
          <ul className="max-h-72 space-y-2 overflow-y-auto">
            {data.map((v) => (
              <li key={v.id} className="flex items-center justify-between gap-2 rounded-md border p-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium">v{v.version}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {v.reason ?? "snapshot"} · {new Date(v.created_at).toLocaleString()}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 shrink-0 px-2"
                  onClick={() =>
                    restore.mutate(v.id, {
                      onSuccess: () => toast.success(`Restored v${v.version}`),
                      onError: () => toast.error("Restore failed"),
                    })
                  }
                >
                  <RotateCcw className="mr-1 h-3.5 w-3.5" />
                  Restore
                </Button>
              </li>
            ))}
          </ul>
        )}
      </PopoverContent>
    </Popover>
  );
}
