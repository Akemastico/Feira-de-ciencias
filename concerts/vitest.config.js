import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    environmentOptions: { jsdom: { url: 'http://localhost:8000/' } },
    include: ['frontend/tests/**/*.test.js'],
  },
});
