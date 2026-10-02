"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Persona } from "@/lib/persona";
import { useUpdateIdentity } from "@/hooks/use-persona";
import { ApiError } from "@/lib/api";

export function IdentityCard({ persona }: { persona: Persona }) {
  const update = useUpdateIdentity();
  const [form, setForm] = useState({
    full_name: persona.full_name ?? "",
    headline: persona.headline ?? "",
    location: persona.location ?? "",
    summary: persona.summary ?? "",
  });

  function set(k: keyof typeof form, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function save() {
    try {
      await update.mutateAsync({
        full_name: form.full_name || null,
        headline: form.headline || null,
        location: form.location || null,
        summary: form.summary || null,
      });
      toast.success("Identity saved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Save failed");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Identity</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="full_name">Full name</Label>
            <Input id="full_name" value={form.full_name} onChange={(e) => set("full_name", e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="headline">Headline</Label>
            <Input
              id="headline"
              placeholder="e.g. AI Engineer"
              value={form.headline}
              onChange={(e) => set("headline", e.target.value)}
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="location">Location</Label>
          <Input id="location" value={form.location} onChange={(e) => set("location", e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="summary">Summary</Label>
          <Textarea
            id="summary"
            rows={4}
            value={form.summary}
            onChange={(e) => set("summary", e.target.value)}
          />
        </div>
        <Button onClick={save} disabled={update.isPending}>
          {update.isPending ? "Saving…" : "Save identity"}
        </Button>
      </CardContent>
    </Card>
  );
}
