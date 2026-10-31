import type { NextConfig } from "next";

const config: NextConfig = {
  poweredByHeader: false,
  devIndicators: false,
  logging: { incomingRequests: false },
};
export default config;
