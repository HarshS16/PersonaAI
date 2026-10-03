import { api } from "@/lib/api";

export type Source = {
  id: string;
  type: string;
  provider: string | null;
  title: string | null;
  url: string | null;
  status: string;
  last_synced: string | null;
  stats: Record<string, unknown>;
  error: string | null;
  created_at: string;
};

export type Job = {
  id: string;
  source_id: string | null;
  type: string;
  status: "queued" | "running" | "succeeded" | "failed";
  progress: number;
  step: string | null;
  error: string | null;
  result: {
    created?: Record<string, number>;
    updated?: Record<string, number>;
    evidence_added?: number;
    conflicts?: number;
  };
  created_at: string;
  updated_at: string;
};

export type UploadResponse = {
  source: Source;
  job: Job;
  duplicate: boolean;
};

export type Conflict = {
  id: string;
  field: string;
  candidates: { value: string; source: string }[];
  status: string;
  resolution: Record<string, unknown>;
  created_at: string;
};

export type GitHubStatus = {
  oauth_connected: boolean;
  username: string | null;
  source_id: string | null;
};

export const githubApi = {
  status: () => api<GitHubStatus>("/sources/github/status"),
  connect: (username?: string) =>
    api<{ source: Source; job: Job }>("/sources/github/connect", {
      method: "POST",
      body: JSON.stringify({ username: username || null }),
    }),
  sync: (sourceId: string) =>
    api<Job>(`/sources/github/${sourceId}/sync`, { method: "POST" }),
};

async function _uploadFile(
  endpoint: string,
  file: File,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`/api/backend${endpoint}`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error ?? {};
    throw new Error(err.message ?? "Upload failed");
  }
  return body as UploadResponse;
}

export const researchApi = {
  connect: (provider: string, query: string) =>
    api<{ source: Source; job: Job }>("/sources/research/connect", {
      method: "POST",
      body: JSON.stringify({ provider, query }),
    }),
};

export const blogApi = {
  connect: (provider: string, handle: string) =>
    api<{ source: Source; job: Job }>("/sources/blog/connect", {
      method: "POST",
      body: JSON.stringify({ provider, handle }),
    }),
  sync: (sourceId: string) =>
    api<Job>(`/sources/blog/${sourceId}/sync`, { method: "POST" }),
};

export const sourcesApi = {
  upload: (file: File) => _uploadFile("/documents/upload", file),
  uploadLinkedIn: (file: File) => _uploadFile("/sources/linkedin/upload", file),
  uploadX: (file: File) => _uploadFile("/sources/x/upload", file),
  uploadEmail: (file: File) => _uploadFile("/sources/email/upload", file),
  uploadCalendar: (file: File) => _uploadFile("/sources/calendar/upload", file),
  uploadBookmarks: (file: File) => _uploadFile("/sources/pkm/bookmarks/upload", file),
  uploadNotes: (file: File) => _uploadFile("/sources/pkm/notes/upload", file),

  list: () => api<Source[]>("/sources"),
  disconnect: (id: string) => api<void>(`/sources/${id}`, { method: "DELETE" }),
  getJob: (id: string) => api<Job>(`/jobs/${id}`),
  listConflicts: () => api<Conflict[]>("/conflicts"),
  resolveConflict: (id: string, chosen_value: string) =>
    api<Conflict>(`/conflicts/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify({ chosen_value }),
    }),
};
