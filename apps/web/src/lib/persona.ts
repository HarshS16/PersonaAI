import { api } from "@/lib/api";

export type Visibility = "private" | "shared" | "public";
export type EvidenceState = "verified" | "inferred" | "user_confirmed" | "unknown";

export type Persona = {
  id: string;
  version: number;
  status: string;
  full_name: string | null;
  headline: string | null;
  summary: string | null;
  location: string | null;
  links: Record<string, unknown>;
  completeness: number;
  created_at: string;
  updated_at: string;
};

export type FactMeta = {
  id: string;
  visibility: Visibility;
  state: EvidenceState;
  confidence: number;
  created_at: string;
  updated_at: string;
};

// Facts are stored generically; each carries FactMeta plus type-specific fields.
export type Fact = FactMeta & Record<string, unknown>;

export type Evidence = {
  id: string;
  entity_type: string;
  entity_id: string;
  source_id: string | null;
  content: string | null;
  locator: Record<string, unknown>;
  state: EvidenceState;
  confidence: number;
  created_at: string;
};

export type PersonaVersion = {
  id: string;
  version: number;
  reason: string | null;
  created_at: string;
};

export type FullPersona = {
  persona: Persona;
  facts: Record<string, Fact[]>;
};

export const RESOURCES = [
  "skills",
  "experiences",
  "projects",
  "education",
  "achievements",
  "publications",
  "certifications",
  "preferences",
] as const;
export type Resource = (typeof RESOURCES)[number];

export const personaApi = {
  getFull: () => api<FullPersona>("/persona/full"),
  get: () => api<Persona>("/persona"),
  updateIdentity: (data: Partial<Persona>) =>
    api<Persona>("/persona", { method: "PATCH", body: JSON.stringify(data) }),

  listFacts: (resource: string) => api<Fact[]>(`/persona/${resource}`),
  createFact: (resource: string, data: Record<string, unknown>) =>
    api<Fact>(`/persona/${resource}`, { method: "POST", body: JSON.stringify(data) }),
  updateFact: (resource: string, id: string, data: Record<string, unknown>) =>
    api<Fact>(`/persona/${resource}/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteFact: (resource: string, id: string) =>
    api<void>(`/persona/${resource}/${id}`, { method: "DELETE" }),
  confirmFact: (resource: string, id: string) =>
    api<Fact>(`/persona/${resource}/${id}/confirm`, { method: "POST" }),
  factEvidence: (resource: string, id: string) =>
    api<Evidence[]>(`/persona/${resource}/${id}/evidence`),

  listVersions: () => api<PersonaVersion[]>("/persona/meta/versions"),
  restoreVersion: (id: string) =>
    api<Persona>(`/persona/meta/versions/${id}/restore`, { method: "POST" }),
};
