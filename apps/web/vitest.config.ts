import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true, // required for testing-library's automatic DOM cleanup
    // Component tests use .spec.* — the legacy self-contained lib scripts
    // (src/lib/*.test.ts) run separately via tsx in `npm test`.
    include: ["src/**/*.spec.{ts,tsx}"],
    setupFiles: ["./vitest.setup.ts"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});
