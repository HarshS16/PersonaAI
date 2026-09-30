import { api } from "@/lib/api";

export type User = {
  id: string;
  email: string;
  name: string | null;
  role: string;
  email_verified: boolean;
  created_at: string;
};

export type Me = User & {
  oauth_accounts: { provider: string; provider_username: string | null }[];
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
};

export const authApi = {
  signup: (email: string, password: string, name?: string) =>
    api<TokenResponse>("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    }),

  login: (email: string, password: string) =>
    api<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  logout: () => api<void>("/auth/logout", { method: "POST" }),

  me: () => api<Me>("/auth/me"),

  updateProfile: (name: string) =>
    api<User>("/auth/me", { method: "PATCH", body: JSON.stringify({ name }) }),

  forgotPassword: (email: string) =>
    api<{ status: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  resetPassword: (token: string, password: string) =>
    api<void>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }),

  verifyEmail: (token: string) =>
    api<void>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

  changePassword: (current_password: string, new_password: string) =>
    api<void>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),
};

/** Start an OAuth login by navigating to the backend (through the proxy). */
export function oauthLoginUrl(provider: "github" | "google"): string {
  return `/api/backend/auth/${provider}/login`;
}
