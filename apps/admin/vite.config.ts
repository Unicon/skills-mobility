import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Dev proxy forwards read routes to the local Orchestrator FastAPI service,
// so the SPA runs same-origin in the browser (no CORS).
const BACKEND = "http://127.0.0.1:8400";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      "/executions": { target: BACKEND, changeOrigin: true },
      "/healthz": { target: BACKEND, changeOrigin: true },
      // The demo-reset cascade starts at the Mock LMS (which forwards to the
      // Event Consumer → Orchestrator); deployed, a CloudFront behavior routes
      // /demo/* to the mock-lms origin the same way.
      "/demo": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
  },
});
