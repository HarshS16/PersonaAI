"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { sourcesApi, type Job } from "@/lib/sources";

export function useSources() {
  return useQuery({ queryKey: ["sources"], queryFn: sourcesApi.list });
}

export function useConflicts() {
  return useQuery({ queryKey: ["conflicts"], queryFn: sourcesApi.listConflicts });
}

/** Poll a job until it finishes. */
export function useJob(jobId: string | null) {
  return useQuery<Job>({
    queryKey: ["job", jobId],
    queryFn: () => sourcesApi.getJob(jobId as string),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "succeeded" || status === "failed" ? false : 1200;
    },
  });
}

export function useDisconnectSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => sourcesApi.disconnect(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sources"] });
      qc.invalidateQueries({ queryKey: ["persona"] });
    },
  });
}

export function useResolveConflict() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) =>
      sourcesApi.resolveConflict(id, value),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["conflicts"] });
      qc.invalidateQueries({ queryKey: ["persona"] });
    },
  });
}
