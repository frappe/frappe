const { defineConfig, devices } = require("@playwright/test");

/**
 * Read environment variables
 */
const baseURL = process.env.PLAYWRIGHT_baseURL || "http://localhost:8000";
const adminPassword = process.env.ADMIN_PASSWORD || "admin";

/**
 * @see https://playwright.dev/docs/test-configuration
 */
module.exports = defineConfig({
	testDir: "./playwright/tests",
	/* Run tests in files in parallel */
	fullyParallel: true,
	/* Fail the build on CI if you accidentally left test.only in the source code. */
	forbidOnly: !!process.env.CI,
	/* Retry on CI only */
	retries: process.env.CI ? 2 : 0,
	/* Opt out of parallel tests on CI. */
	workers: process.env.CI ? 1 : undefined,
	/* Reporter to use. See https://playwright.dev/docs/test-reporters */
	reporter: "html",
	/* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
	use: {
		/* Base URL to use in actions like `await page.goto('/')`. */
		baseURL: baseURL,
		/* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
		trace: "on-first-retry",
		/* Screenshot on failure */
		screenshot: "only-on-failure",
		/* Video on failure */
		video: "retain-on-failure",
	},

	/* Configure projects for major browsers */
	projects: [
		{
			name: "chromium",
			use: {
				...devices["Desktop Chrome"],
				/* Reuse browser context to avoid opening multiple windows */
				launchOptions: {
					args: ["--disable-dev-shm-usage"],
				},
			},
		},

		{
			name: "firefox",
			use: { ...devices["Desktop Firefox"] },
		},

		{
			name: "webkit",
			use: { ...devices["Desktop Safari"] },
		},
	],
});
