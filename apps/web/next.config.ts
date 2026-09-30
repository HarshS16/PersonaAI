import type { NextConfig } from "next";

/**
 * API requests from the browser go to the same origin under `/api/*` and are
 * proxied to the FastAPI backend. This keeps auth cookies first-party and means
 * OAuth tokens never reach client JS (SRD §36).
 */
const API_BASE = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${API_BASE}/:path*`,
      },
    ];
  },
};

export default nextConfig;
