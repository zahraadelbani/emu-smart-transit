import { defineConfig } from "@playwright/test";
import { randomBytes } from "node:crypto";
import { resolve } from "node:path";

process.env.E2E_PASSWORD ||= randomBytes(24).toString("hex");
const env = {
  ...process.env,
  DEBUG: "true",
  DEMO_MODE: "true",
  LIVE_SECONDS: "3",
  OFFLINE_SECONDS: "7",
  GPS_POLL_SECONDS: "1",
  SQLITE_PATH: resolve("../backend/e2e.sqlite3"),
};
export default defineConfig({
  testDir: "./tests/e2e",
  workers: 1,
  timeout: 45000,
  use: {
    baseURL: "http://127.0.0.1:5173",
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "python ../scripts/e2e_server.py",
      url: "http://127.0.0.1:8000/health/",
      reuseExistingServer: false,
      env,
      timeout: 60000,
    },
    {
      command: "npm run dev",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
      env,
      timeout: 60000,
    },
  ],
});
