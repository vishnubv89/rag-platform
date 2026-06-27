import { defineConfig } from "vite";

export default defineConfig({
  build: {
    lib: {
      entry: "src/main.ts",
      name: "KMChatWidget",
      fileName: () => "chat-widget.js",
      formats: ["iife"],
    },
    outDir: "../dist-widget",
    emptyOutDir: false,
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
      },
    },
    minify: true,
  },
});
