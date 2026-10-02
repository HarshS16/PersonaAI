"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { personaApi, type FullPersona, type Persona } from "@/lib/persona";

const FULL_KEY = ["persona", "full"];

export function usePersonaFull() {
  return useQuery<FullPersona>({ queryKey: FULL_KEY, queryFn: personaApi.getFull });
}

export function useInvalidatePersona() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["persona"] });
}

export function useUpdateIdentity() {
  const invalidate = useInvalidatePersona();
  return useMutation({
    mutationFn: (data: Partial<Persona>) => personaApi.updateIdentity(data),
    onSuccess: invalidate,
  });
}

export function useCreateFact(resource: string) {
  const invalidate = useInvalidatePersona();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => personaApi.createFact(resource, data),
    onSuccess: invalidate,
  });
}

export function useUpdateFact(resource: string) {
  const invalidate = useInvalidatePersona();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      personaApi.updateFact(resource, id, data),
    onSuccess: invalidate,
  });
}

export function useDeleteFact(resource: string) {
  const invalidate = useInvalidatePersona();
  return useMutation({
    mutationFn: (id: string) => personaApi.deleteFact(resource, id),
    onSuccess: invalidate,
  });
}

export function useConfirmFact(resource: string) {
  const invalidate = useInvalidatePersona();
  return useMutation({
    mutationFn: (id: string) => personaApi.confirmFact(resource, id),
    onSuccess: invalidate,
  });
}

export function usePersonaVersions() {
  return useQuery({ queryKey: ["persona", "versions"], queryFn: personaApi.listVersions });
}

export function useRestoreVersion() {
  const invalidate = useInvalidatePersona();
  return useMutation({
    mutationFn: (id: string) => personaApi.restoreVersion(id),
    onSuccess: invalidate,
  });
}
