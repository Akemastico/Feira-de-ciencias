import { defineConfig, devices } from '@playwright/test';

const python = process.platform === 'win32'
  ? '.venv\\Scripts\\python.exe'
  : '.venv/bin/python';

export default defineConfig({
  testDir: './frontend/tests_e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: 'http://127.0.0.1:8010',
    trace: 'on-first-retry',
    permissions: ['microphone'],
    launchOptions: {
      args: [
        '--use-fake-ui-for-media-stream',
        '--use-fake-device-for-media-stream',
        '--autoplay-policy=no-user-gesture-required',
      ],
    },
  },
  webServer: {
    command: `${python} -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010`,
    cwd: import.meta.dirname,
    url: 'http://127.0.0.1:8010/',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    env: { BMO_PRELOAD: '0', LOG_TO_FILE: '0', BMO_E2E: '1' },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
