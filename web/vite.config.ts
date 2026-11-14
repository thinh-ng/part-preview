import { fileURLToPath } from "node:url"
import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

// `npm run dev` serves the page on 5173 and forwards the API to the Python server on 8765.
export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { proxy: { "/api": { target: "http://127.0.0.1:8765", changeOrigin: true } } },
  // Budget for the single bundle; three.js alone is about 600 kB minified.
  build: { chunkSizeWarningLimit: 900 },
})
