import type { NextConfig } from "next";

// Backend runs internally on this port (see ../.env BACKEND_PORT). Both
// backend and frontend are exposed to the internet through the single
// Cloudflare Tunnel URL that points at this Next.js process (PM2 process
// `hslab-app`), so API calls are proxied here rather than exposed on a
// second public port.
const backendPort = process.env.BACKEND_PORT ?? "8000";
const backendOrigin = `http://127.0.0.1:${backendPort}`;

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backendOrigin}/api/:path*` },
      { source: "/admin/:path*", destination: `${backendOrigin}/admin/:path*` },
    ];
  },
};

export default nextConfig;
