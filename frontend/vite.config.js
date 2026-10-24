import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/datasets": "http://localhost:8000",
      "/jobs": "http://localhost:8000",
      "/models": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/assistant": "http://localhost:8000",
      "/auth": "http://localhost:8000"
    }
  }
});
