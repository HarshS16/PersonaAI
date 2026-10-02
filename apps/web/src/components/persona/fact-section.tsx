"use client";

import { useState } from "react";
import { Plus, Pencil, Trash2, Check } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { RESOURCE_CONFIG } from "@/lib/fact-fields";
import type { Fact, Resource } from "@/lib/persona";
import { useCreateFact, useUpdateFact, useDeleteFact, useConfirmFact } from "@/hooks/use-persona";
import { FactFormDialog } from "./fact-form-dialog";
import { EvidencePopover } from "./evidence-popover";

export function FactSection({ resource, facts }: { resource: Resource; facts: Fact[] }) {
  const config = RESOURCE_CONFIG[resource];
  const create = useCreateFact(resource);
  const update = useUpdateFact(resource);
  const remove = useDeleteFact(resource);
  const confirm = useConfirmFact(resource);

  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Fact | null>(null);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">
          {config.plural} · {facts.length}
        </h3>
        <Button size="sm" variant="outline" onClick={() => setAdding(true)}>
          <Plus className="mr-1 h-4 w-4" />
          Add
        </Button>
      </div>

      {facts.length === 0 ? (
        <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
          No {config.plural.toLowerCase()} yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {facts.map((f) => (
            <li
              key={f.id}
              className="flex items-start justify-between gap-3 rounded-md border p-3"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate font-medium">{config.title(f) || "(untitled)"}</span>
                  {f.state === "inferred" && (
                    <Badge variant="outline" className="text-[10px]">
                      inferred
                    </Badge>
                  )}
                  {f.visibility !== "private" && (
                    <Badge variant="secondary" className="text-[10px]">
                      {f.visibility}
                    </Badge>
                  )}
                </div>
                {config.subtitle(f) && (
                  <p className="truncate text-sm text-muted-foreground">{config.subtitle(f)}</p>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <EvidencePopover resource={resource} factId={f.id} />
                {f.state === "inferred" && (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 px-2"
                    title="Confirm"
                    onClick={() =>
                      confirm.mutate(f.id, { onSuccess: () => toast.success("Confirmed") })
                    }
                  >
                    <Check className="h-4 w-4" />
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 px-2"
                  title="Edit"
                  onClick={() => setEditing(f)}
                >
                  <Pencil className="h-4 w-4" />
                </Button>
                <DeleteButton onConfirm={() => remove.mutate(f.id)} />
              </div>
            </li>
          ))}
        </ul>
      )}

      {adding && (
        <FactFormDialog
          open={adding}
          onOpenChange={setAdding}
          config={config}
          onSubmit={(data) => create.mutateAsync(data)}
        />
      )}
      {editing && (
        <FactFormDialog
          open={!!editing}
          onOpenChange={(o) => !o && setEditing(null)}
          config={config}
          fact={editing}
          onSubmit={(data) => update.mutateAsync({ id: editing.id, data })}
        />
      )}
    </div>
  );
}

function DeleteButton({ onConfirm }: { onConfirm: () => void }) {
  return (
    <AlertDialog>
      <AlertDialogTrigger
        render={
          <Button size="sm" variant="ghost" className="h-7 px-2 text-destructive" title="Delete" />
        }
      >
        <Trash2 className="h-4 w-4" />
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete this item?</AlertDialogTitle>
          <AlertDialogDescription>This can be recovered from version history.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm}>Delete</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
