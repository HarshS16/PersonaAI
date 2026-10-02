"use client";

import { useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { FieldDef, ResourceConfig } from "@/lib/fact-fields";
import type { Fact } from "@/lib/persona";
import { ApiError } from "@/lib/api";

type Values = Record<string, unknown>;

function initialValues(config: ResourceConfig, fact?: Fact): Values {
  const v: Values = {};
  for (const f of config.fields) {
    if (fact && fact[f.name] != null) v[f.name] = fact[f.name];
    else if (f.type === "tags") v[f.name] = [];
    else if (f.type === "checkbox") v[f.name] = false;
    else if (f.type === "select" && f.options?.length) v[f.name] = f.options[0].value;
    else v[f.name] = "";
  }
  return v;
}

export function FactFormDialog({
  open,
  onOpenChange,
  config,
  fact,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  config: ResourceConfig;
  fact?: Fact;
  onSubmit: (data: Values) => Promise<unknown>;
}) {
  const [values, setValues] = useState<Values>(() => initialValues(config, fact));
  const [submitting, setSubmitting] = useState(false);

  function set(name: string, value: unknown) {
    setValues((v) => ({ ...v, [name]: value }));
  }

  async function handleSubmit() {
    // Strip empty optional fields so the backend keeps nulls.
    const payload: Values = {};
    for (const f of config.fields) {
      const val = values[f.name];
      if (f.type === "tags") {
        payload[f.name] = val;
      } else if (f.type === "number") {
        payload[f.name] = val === "" || val == null ? null : Number(val);
      } else if (val === "" || val == null) {
        if (f.required) {
          toast.error(`${f.label} is required`);
          return;
        }
        payload[f.name] = f.type === "checkbox" ? false : null;
      } else {
        payload[f.name] = val;
      }
    }

    setSubmitting(true);
    try {
      await onSubmit(payload);
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {fact ? "Edit" : "Add"} {config.singular.toLowerCase()}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {config.fields.map((f) => (
            <Field key={f.name} def={f} value={values[f.name]} onChange={(v) => set(f.name, v)} />
          ))}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Field({
  def,
  value,
  onChange,
}: {
  def: FieldDef;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  if (def.type === "checkbox") {
    return (
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(e) => onChange(e.target.checked)}
          className="h-4 w-4"
        />
        {def.label}
      </label>
    );
  }

  return (
    <div className="space-y-2">
      <Label htmlFor={def.name}>
        {def.label}
        {def.required && <span className="text-destructive"> *</span>}
      </Label>
      {def.type === "textarea" ? (
        <Textarea
          id={def.name}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
        />
      ) : def.type === "select" ? (
        <Select value={String(value ?? "")} onValueChange={onChange}>
          <SelectTrigger id={def.name}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {def.options?.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : def.type === "tags" ? (
        <Input
          id={def.name}
          value={Array.isArray(value) ? (value as string[]).join(", ") : ""}
          placeholder="Comma-separated"
          onChange={(e) =>
            onChange(
              e.target.value
                .split(",")
                .map((t) => t.trim())
                .filter(Boolean),
            )
          }
        />
      ) : (
        <Input
          id={def.name}
          type={def.type === "number" ? "number" : def.type === "date" ? "date" : "text"}
          value={String(value ?? "")}
          placeholder={def.placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </div>
  );
}
