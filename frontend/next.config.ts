import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  eslint: {
    // Frontend build should not fail when eslint is not installed in CI/sandbox
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
