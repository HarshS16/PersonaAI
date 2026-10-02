import { api } from "@/lib/api";

export type JDAnalysis = {
  title: string | null;
  required_skills: string[];
  preferred_skills: string[];
  technologies: string[];
  responsibilities: string[];
  experience_years: number | null;
  education: string | null;
  domain: string | null;
};

export type RequirementMatch = {
  requirement: string;
  kind: "required" | "preferred";
  status: "strong" | "partial" | "none";
  evidence: string[];
};

export type Gap = {
  strongly_supported: string[];
  partially_supported: string[];
  not_demonstrated: string[];
};

export type JDResult = {
  id: string;
  analysis: JDAnalysis;
  matches: RequirementMatch[];
  gap: Gap;
};

export type Bullet = { text: string; validated: boolean; softened?: boolean };

export type ResumeResult = {
  id: string;
  resume: {
    name: string | null;
    headline: string;
    summary: string;
    skills: string[];
    experience: {
      role: string;
      company: string | null;
      start_date: string | null;
      end_date: string | null;
      bullets: Bullet[];
      evidence: string[];
    }[];
    projects: { name: string; technologies: string[]; bullets: Bullet[]; url: string | null; evidence: string[] }[];
    education: { institution: string; degree: string | null; field_of_study: string | null }[];
  };
  markdown: string;
  matched_requirements: string[];
  missing_requirements: string[];
  gap: Gap;
  ats: { keyword_coverage: number; covered: string[]; missing: string[] };
};

export type InterviewResult = {
  id: string;
  mode: string;
  questions: { question: string; focus: string }[];
};

export const careerApi = {
  analyzeJd: (job_description: string) =>
    api<JDResult>("/jd/analyze", { method: "POST", body: JSON.stringify({ job_description }) }),
  generateResume: (job_description: string, target_role?: string) =>
    api<ResumeResult>("/resume/generate", {
      method: "POST",
      body: JSON.stringify({ job_description, target_role: target_role || null }),
    }),
  startInterview: (mode: string, job_description?: string) =>
    api<InterviewResult>("/interview/start", {
      method: "POST",
      body: JSON.stringify({ mode, job_description: job_description || null }),
    }),
};
