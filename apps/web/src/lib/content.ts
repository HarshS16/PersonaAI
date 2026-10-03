import { api } from "@/lib/api";

export type ContentResult = {
  id: string;
  content: string;
  warnings: string[];
  content_type?: string;
  tone?: string;
  matched?: string[];
  missing?: string[];
};

export const contentApi = {
  generate: (content_type: string, topic: string, tone: string) =>
    api<ContentResult>("/content/generate", {
      method: "POST",
      body: JSON.stringify({ content_type, topic, tone }),
    }),
  coverLetter: (job_description: string, company: string, tone: string) =>
    api<ContentResult>("/content/cover-letter", {
      method: "POST",
      body: JSON.stringify({ job_description, company: company || null, tone }),
    }),
  applicationAnswer: (question: string, job_description?: string) =>
    api<ContentResult>("/content/application-answer", {
      method: "POST",
      body: JSON.stringify({ question, job_description: job_description || null }),
    }),
  proposal: (project_description: string, platform: string, tone: string) =>
    api<ContentResult>("/content/proposal", {
      method: "POST",
      body: JSON.stringify({ project_description, platform, tone }),
    }),
  meetingPrep: (context: string, focus: string) =>
    api<{ id: string; content: string; focus: string }>("/content/meeting-prep", {
      method: "POST",
      body: JSON.stringify({ context, focus }),
    }),
};
