import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev proxy forwards API calls to the local mock-lms FastAPI service,
// so the SPA runs same-origin in the browser (no CORS).
const BACKEND = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true },
      "/demo": { target: BACKEND, changeOrigin: true },
      "/healthz": { target: BACKEND, changeOrigin: true },
    },
  },
});
