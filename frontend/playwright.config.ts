import { defineConfig } from "@playwright/test";
import { randomBytes } from "node:crypto";

// Synthetic credentials exist only in the test process environment, not in source/output files.
process.env.SUBCADENCE_TEST_PASSWORD ||= `Aa!${randomBytes(24).toString("base64url")}`;
process.env.AUTH_SECRET_KEY ||= randomBytes(48).toString("base64url");
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: { timeout: 15000 },
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    viewport: { width: 1440, height: 1000 },
    trace: "off",
    screenshot: "only-on-failure",
    browserName: "chromium",
  },
  webServer: [
    {
      command: "node scripts/test-backend.mjs",
      url: "http://127.0.0.1:8766/api/v1/health",
      reuseExistingServer: false,
      timeout: 60000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:3000/login",
      env: {
        NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8766/api/v1",
        NEXT_TELEMETRY_DISABLED: "1",
      },
      reuseExistingServer: false,
      timeout: 120000,
    },
  ],
});
