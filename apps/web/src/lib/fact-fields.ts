import type { Fact, Resource } from "@/lib/persona";

export type FieldType = "text" | "textarea" | "number" | "date" | "tags" | "select" | "checkbox";

export type FieldDef = {
  name: string;
  label: string;
  type: FieldType;
  required?: boolean;
  options?: { label: string; value: string }[];
  placeholder?: string;
};

export type ResourceConfig = {
  singular: string;
  plural: string;
  /** Primary line shown in the list. */
  title: (f: Fact) => string;
  /** Secondary line shown in the list. */
  subtitle: (f: Fact) => string;
  fields: FieldDef[];
};

const EMPLOYMENT_TYPES = [
  { label: "Job", value: "job" },
  { label: "Internship", value: "internship" },
  { label: "Freelance", value: "freelance" },
  { label: "Open source", value: "open_source" },
  { label: "Volunteer", value: "volunteer" },
  { label: "Leadership", value: "leadership" },
];

const s = (f: Fact, k: string) => (f[k] == null ? "" : String(f[k]));

export const RESOURCE_CONFIG: Record<Resource, ResourceConfig> = {
  skills: {
    singular: "Skill",
    plural: "Skills",
    title: (f) => s(f, "name"),
    subtitle: (f) => s(f, "category"),
    fields: [
      { name: "name", label: "Name", type: "text", required: true },
      { name: "category", label: "Category", type: "text", placeholder: "e.g. Programming" },
    ],
  },
  experiences: {
    singular: "Experience",
    plural: "Experience",
    title: (f) => s(f, "role"),
    subtitle: (f) => s(f, "company"),
    fields: [
      { name: "role", label: "Role", type: "text", required: true },
      { name: "company", label: "Company", type: "text" },
      { name: "employment_type", label: "Type", type: "select", options: EMPLOYMENT_TYPES },
      { name: "location", label: "Location", type: "text" },
      { name: "start_date", label: "Start date", type: "date" },
      { name: "end_date", label: "End date", type: "date" },
      { name: "is_current", label: "Current role", type: "checkbox" },
      { name: "description", label: "Description", type: "textarea" },
      { name: "highlights", label: "Highlights", type: "tags" },
    ],
  },
  projects: {
    singular: "Project",
    plural: "Projects",
    title: (f) => s(f, "name"),
    subtitle: (f) => s(f, "role"),
    fields: [
      { name: "name", label: "Name", type: "text", required: true },
      { name: "role", label: "Role", type: "text" },
      { name: "description", label: "Description", type: "textarea" },
      { name: "technologies", label: "Technologies", type: "tags" },
      { name: "outcomes", label: "Outcomes", type: "tags" },
      { name: "repository_url", label: "Repository URL", type: "text" },
      { name: "url", label: "Live URL", type: "text" },
      { name: "start_date", label: "Start date", type: "date" },
      { name: "end_date", label: "End date", type: "date" },
    ],
  },
  education: {
    singular: "Education",
    plural: "Education",
    title: (f) => s(f, "institution"),
    subtitle: (f) => [s(f, "degree"), s(f, "field_of_study")].filter(Boolean).join(", "),
    fields: [
      { name: "institution", label: "Institution", type: "text", required: true },
      { name: "degree", label: "Degree", type: "text" },
      { name: "field_of_study", label: "Field of study", type: "text" },
      { name: "start_date", label: "Start date", type: "date" },
      { name: "end_date", label: "End date", type: "date" },
      { name: "grade", label: "Grade", type: "text" },
      { name: "description", label: "Description", type: "textarea" },
    ],
  },
  achievements: {
    singular: "Achievement",
    plural: "Achievements",
    title: (f) => s(f, "title"),
    subtitle: (f) => s(f, "issuer"),
    fields: [
      { name: "title", label: "Title", type: "text", required: true },
      { name: "issuer", label: "Issuer", type: "text" },
      { name: "date_awarded", label: "Date", type: "date" },
      { name: "description", label: "Description", type: "textarea" },
    ],
  },
  publications: {
    singular: "Publication",
    plural: "Research",
    title: (f) => s(f, "title"),
    subtitle: (f) => [s(f, "venue"), s(f, "year")].filter(Boolean).join(", "),
    fields: [
      { name: "title", label: "Title", type: "text", required: true },
      { name: "venue", label: "Venue", type: "text" },
      { name: "year", label: "Year", type: "number" },
      { name: "url", label: "URL", type: "text" },
      { name: "authors", label: "Authors", type: "tags" },
      { name: "description", label: "Description", type: "textarea" },
    ],
  },
  certifications: {
    singular: "Certification",
    plural: "Certifications",
    title: (f) => s(f, "name"),
    subtitle: (f) => s(f, "issuer"),
    fields: [
      { name: "name", label: "Name", type: "text", required: true },
      { name: "issuer", label: "Issuer", type: "text" },
      { name: "issue_date", label: "Issue date", type: "date" },
      { name: "expiry_date", label: "Expiry date", type: "date" },
      { name: "credential_id", label: "Credential ID", type: "text" },
      { name: "url", label: "URL", type: "text" },
    ],
  },
  preferences: {
    singular: "Preference",
    plural: "Preferences",
    title: (f) => s(f, "key"),
    subtitle: (f) => s(f, "value"),
    fields: [
      { name: "key", label: "Key", type: "text", required: true, placeholder: "e.g. Remote" },
      { name: "value", label: "Value", type: "text", required: true, placeholder: "e.g. Preferred" },
    ],
  },
};
