import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '..', '');
  return {
    plugins: [react()],
    resolve: {
      alias: {
        'monaco-editor/esm': fileURLToPath(
          new URL('./node_modules/monaco-editor/esm', import.meta.url),
        ),
      },
    },
    optimizeDeps: { exclude: ['monaco-editor'] },
    server: { port: Number(env.FRONTEND_CONTAINER_PORT ?? env.FRONTEND_TEST_PORT ?? 5173) },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test-setup.ts',
      exclude: ['e2e/**', 'node_modules/**'],
    },
  };
});
