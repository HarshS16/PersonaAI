import { api } from "@/lib/api";

export type JobLead = {
  id: string;
  title: string;
  company: string | null;
  url: string | null;
  location: string | null;
  description: string | null;
  fit_score: number;
  fit_explanation: string | null;
  matched_skills: string[];
  missing_skills: string[];
  approval_status: string;
};

export type SearchTask = {
  id: string;
  query: string;
  criteria: Record<string, unknown>;
  status: string;
  results_count: number;
  created_at: string;
};

export type SearchResult = {
  task: SearchTask;
  leads: JobLead[];
};

export type ApplicationResult = {
  id: string;
  cover_letter: string;
  job_title: string;
  company: string | null;
  fit_score: number;
  matched_skills: string[];
  missing_skills: string[];
};

export const jobSearchApi = {
  search: (query: string, criteria?: Record<string, unknown>) =>
    api<SearchResult>("/agent/jobs/search", {
      method: "POST",
      body: JSON.stringify({ query, criteria: criteria ?? null }),
    }),
  listTasks: () => api<SearchTask[]>("/agent/jobs/tasks"),
  getTask: (id: string) => api<SearchTask>(`/agent/jobs/tasks/${id}`),
  getLeads: (taskId: string) =>
    api<JobLead[]>(`/agent/jobs/tasks/${taskId}/leads`),
  approveLead: (leadId: string) =>
    api<JobLead>(`/agent/jobs/leads/${leadId}/approve`, { method: "POST" }),
  rejectLead: (leadId: string) =>
    api<JobLead>(`/agent/jobs/leads/${leadId}/reject`, { method: "POST" }),
  applyToLead: (leadId: string) =>
    api<ApplicationResult>(`/agent/jobs/leads/${leadId}/apply`, {
      method: "POST",
    }),
};
