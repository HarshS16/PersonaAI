"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { authApi, type Me } from "@/lib/auth";
import { ApiError } from "@/lib/api";

const ME_KEY = ["me"];

export function useMe() {
  return useQuery<Me>({
    queryKey: ME_KEY,
    queryFn: authApi.me,
    retry: (count, err) => {
      // Don't retry an unauthenticated response.
      if (err instanceof ApiError && err.status === 401) return false;
      return count < 1;
    },
    staleTime: 60_000,
  });
}

export function useLogout() {
  const qc = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: authApi.logout,
    onSettled: () => {
      qc.clear();
      router.push("/login");
    },
  });
}
