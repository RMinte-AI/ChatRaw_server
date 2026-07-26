import { defineConfig, devices } from '@playwright/test';

const serverPort = 51151;
const modulePort = 8768;
const modelPort = 51152;

export default defineConfig({
    testDir: './browser-tests',
    timeout: 60_000,
    fullyParallel: false,
    workers: 1,
    forbidOnly: Boolean(process.env.CI),
    retries: process.env.CI ? 1 : 0,
    reporter: process.env.CI ? 'github' : 'line',
    use: {
        baseURL: `http://127.0.0.1:${serverPort}`,
        trace: 'retain-on-failure'
    },
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] }
        },
        {
            name: 'webkit',
            use: { ...devices['Desktop Safari'] }
        },
        {
            name: 'mobile-webkit',
            use: { ...devices['iPhone 13'] }
        }
    ],
    webServer: [
        {
            command: [
                'T6_FRONTEND_MODE=resident',
                'T6_SOURCE_HOLD_AFTER_BOOTSTRAP=1',
                'RATE_LIMIT_ENABLED=false',
                `T6_SOURCE_SERVER_PORT=${serverPort}`,
                `T6_SOURCE_MODULE_PORT=${modulePort}`,
                './scripts/run-t6-source-gate.sh'
            ].join(' '),
            url: `http://127.0.0.1:${serverPort}/health`,
            timeout: 120_000,
            reuseExistingServer: false,
            gracefulShutdown: {
                signal: 'SIGTERM',
                timeout: 10_000
            }
        },
        {
            command: [
                'exec python scripts/t7-model-fixture.py',
                '--host 127.0.0.1',
                `--port ${modelPort}`
            ].join(' '),
            url: `http://127.0.0.1:${modelPort}/health`,
            timeout: 30_000,
            reuseExistingServer: false,
            gracefulShutdown: {
                signal: 'SIGTERM',
                timeout: 5_000
            }
        }
    ]
});
