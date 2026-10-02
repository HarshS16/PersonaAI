"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { usePersonaFull } from "@/hooks/use-persona";
import { RESOURCES, type Resource } from "@/lib/persona";
import { RESOURCE_CONFIG } from "@/lib/fact-fields";
import { IdentityCard } from "@/components/persona/identity-card";
import { FactSection } from "@/components/persona/fact-section";
import { VersionHistory } from "@/components/persona/version-history";

export default function PersonaPage() {
  const { data, isLoading } = usePersonaFull();

  if (isLoading || !data) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const { persona, facts } = data;
  const pct = Math.round(persona.completeness * 100);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Your Persona</h2>
          <p className="mt-1 text-muted-foreground">
            Everything here is editable and evidence-backed.
          </p>
        </div>
        <VersionHistory />
      </div>

      <div className="rounded-lg border p-4">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-medium">Profile completeness</span>
          <span className="text-muted-foreground">{pct}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <IdentityCard persona={persona} />

      <Tabs defaultValue="skills">
        <TabsList className="flex h-auto flex-wrap justify-start">
          {RESOURCES.map((r) => (
            <TabsTrigger key={r} value={r}>
              {RESOURCE_CONFIG[r].plural}
            </TabsTrigger>
          ))}
        </TabsList>
        {RESOURCES.map((r) => (
          <TabsContent key={r} value={r} className="mt-4">
            <FactSection resource={r as Resource} facts={facts[r] ?? []} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
