import { defineConfig } from "vite";

// The backend already allows http://localhost:5173 through CORS. The proxy lets the app use a
// same-origin base (VITE_API_BASE_URL=/api/v1) when it is served from another host or port.
export default defineConfig({
  oxc: { jsx: { runtime: "automatic" } },
  server: { proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } } },
});
