import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development, proxy API calls to the FastAPI backend so the frontend
// can use same-origin "/api" paths (which also work behind nginx in Docker).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
