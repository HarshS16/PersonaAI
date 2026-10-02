import { api } from "@/lib/api";

export type DashboardData = {
  greeting_name: string | null;
  completeness: number;
  counts: {
    skills: number;
    projects: number;
    experiences: number;
    education: number;
    sources: number;
  };
  top_skills: { id: string; name: string; confidence: number; evidence_count: number }[];
  projects: { id: string; name: string; technologies: string[] }[];
  timeline: {
    id: string;
    role: string;
    company: string | null;
    start_date: string | null;
    end_date: string | null;
    is_current: boolean;
  }[];
  sources: {
    id: string;
    type: string;
    title: string | null;
    status: string;
    last_synced: string | null;
  }[];
  recent_activity: { kind: string; text: string; at: string | null }[];
  has_sources: boolean;
};

export type GraphNode = {
  id: string;
  type: "persona" | "skill" | "project" | "experience" | "education";
  label: string;
  confidence?: number;
  evidence_count?: number;
};

export type GraphEdge = { id: string; source: string; target: string; label: string };

export type PersonaGraph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  evidence_total: number;
};

export const dashboardApi = {
  get: () => api<DashboardData>("/dashboard"),
  graph: () => api<PersonaGraph>("/persona/graph"),
};
