"use client";

import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { personaApi } from "@/lib/persona";

const STATE_LABEL: Record<string, string> = {
  verified: "Verified",
  inferred: "Inferred",
  user_confirmed: "You confirmed",
  unknown: "Unknown",
};

export function EvidencePopover({ resource, factId }: { resource: string; factId: string }) {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["evidence", resource, factId],
    queryFn: () => personaApi.factEvidence(resource, factId),
    enabled: false,
  });

  return (
    <Popover onOpenChange={(o) => o && refetch()}>
      <PopoverTrigger
        render={<Button variant="ghost" size="sm" className="h-7 gap-1 px-2 text-xs" />}
      >
        <ShieldCheck className="h-3.5 w-3.5" />
        Evidence
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80">
        <p className="mb-2 text-sm font-medium">Why this is here</p>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : !data || data.length === 0 ? (
          <p className="text-sm text-muted-foreground">No evidence recorded yet.</p>
        ) : (
          <ul className="space-y-2">
            {data.map((e) => (
              <li key={e.id} className="rounded-md border p-2 text-sm">
                <div className="mb-1 flex items-center gap-2">
                  <Badge variant="secondary" className="text-[10px]">
                    {STATE_LABEL[e.state] ?? e.state}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {(e.locator?.origin as string) ?? e.source_id ?? "source"}
                  </span>
                </div>
                {e.content && <p className="text-muted-foreground">{e.content}</p>}
              </li>
            ))}
          </ul>
        )}
      </PopoverContent>
    </Popover>
  );
}
