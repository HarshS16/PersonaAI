import { api } from "@/lib/api";

export type PortfolioResult = {
  id: string;
  portfolio: {
    name: string | null;
    headline: string | null;
    about: string;
    skills: string[];
    experience: unknown[];
    projects: unknown[];
  };
  html: string;
};

export const portfolioApi = {
  generate: (public_only: boolean) =>
    api<PortfolioResult>("/portfolio/generate", {
      method: "POST",
      body: JSON.stringify({ public_only }),
    }),
};
