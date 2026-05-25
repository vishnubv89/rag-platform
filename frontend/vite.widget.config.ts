import { defineConfig } from 'vite';

/**
 * Builds src/widget/index.ts as a self-contained IIFE → dist/chat-widget.js
 * Run separately: npm run build:widget
 * The Dockerfile runs both builds so nginx serves /chat-widget.js.
 */
export default defineConfig({
  build: {
    lib: {
      entry:   'src/widget/index.ts',
      name:    'RAGChatWidget',
      formats: ['iife'],
      fileName: () => 'chat-widget.js',
    },
    outDir:     'dist-widget',
    emptyOutDir: true,
    minify:     true,
    rollupOptions: {
      // No external deps — fully self-contained
      external: [],
    },
  },
});
