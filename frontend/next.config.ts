import type { NextConfig } from "next";

const staticExport = process.env.STATIC_EXPORT === "true";

const nextConfig: NextConfig = {
  output: staticExport ? "export" : "standalone",
  agentRules: false,
  ...(staticExport
    ? {}
    : {
        async rewrites() {
          const backendUrl = process.env.BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8000";
          return [
            {
              source: "/backend/:path*",
              destination: `${backendUrl}/:path*`,
            },
          ];
        },
      }),
};

export default nextConfig;
