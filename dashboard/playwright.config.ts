import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 45000,
  use: { baseURL: "http://127.0.0.1:5173", channel: "chrome", headless: true },
  workers: 1,
});
