"use client";

import { FileText, Plug, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useSources, useDisconnectSource } from "@/hooks/use-sources";
import type { Source } from "@/lib/sources";

const STATUS_VARIANT: Record<string, "secondary" | "outline" | "destructive"> = {
  synced: "secondary",
  processing: "outline",
  pending: "outline",
  error: "destructive",
};

function SourceIcon({ type }: { type: string }) {
  if (type === "resume") return <FileText className="h-4 w-4" />;
  return <Plug className="h-4 w-4" />;
}

export function SourceList() {
  const { data: sources, isLoading } = useSources();
  const disconnect = useDisconnectSource();

  if (isLoading) return <Skeleton className="h-40 w-full" />;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Connected sources</CardTitle>
      </CardHeader>
      <CardContent>
        {!sources || sources.length === 0 ? (
          <p className="text-sm text-muted-foreground">No sources connected yet.</p>
        ) : (
          <ul className="space-y-2">
            {sources.map((s) => (
              <SourceRow
                key={s.id}
                source={s}
                onDisconnect={() =>
                  disconnect.mutate(s.id, {
                    onSuccess: () => toast.success("Source disconnected"),
                  })
                }
              />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function SourceRow({ source, onDisconnect }: { source: Source; onDisconnect: () => void }) {
  const stats = source.stats as { created?: Record<string, number> };
  const created = stats?.created ?? {};
  const totals = Object.values(created).reduce((a, b) => a + b, 0);

  return (
    <li className="flex items-center justify-between gap-3 rounded-md border p-3">
      <div className="flex min-w-0 items-center gap-3">
        <SourceIcon type={source.type} />
        <div className="min-w-0">
          <p className="truncate font-medium">{source.title ?? source.type}</p>
          <p className="text-xs text-muted-foreground">
            {source.last_synced
              ? `Synced ${new Date(source.last_synced).toLocaleString()}`
              : "Not yet synced"}
            {totals > 0 && ` · ${totals} facts`}
          </p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Badge variant={STATUS_VARIANT[source.status] ?? "outline"}>{source.status}</Badge>
        <AlertDialog>
          <AlertDialogTrigger
            render={<Button variant="ghost" size="sm" className="h-7 px-2" title="Disconnect" />}
          >
            <RefreshCw className="h-4 w-4" />
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Disconnect this source?</AlertDialogTitle>
              <AlertDialogDescription>
                Evidence from this source is removed. Facts it contributed remain, but may lose support.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={onDisconnect}>Disconnect</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </li>
  );
}
