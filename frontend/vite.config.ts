import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/static/",
  build: {
    outDir: "../src/car_agent/web",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/chat": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/inventory": "http://127.0.0.1:8000",
      "/vehicles": "http://127.0.0.1:8000",
    },
  },
});
