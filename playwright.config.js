const { defineConfig } = require("@playwright/test");

const ci = Boolean(process.env.CI);

module.exports = defineConfig({
	testDir: "./playwright/tests",
	fullyParallel: false,
	workers: 1,
	forbidOnly: ci,
	retries: 1,
	timeout: 120000,
	expect: { timeout: 20000 },
	reporter: ci ? [["list"], ["github"], ["html", { open: "never" }]] : [["list"]],
	use: {
		baseURL: process.env.BASE_URL || "http://localhost:8000",
		viewport: { width: 1400, height: 960 },
		actionTimeout: 20000,
		navigationTimeout: 30000,
		trace: "on-first-retry",
		screenshot: "only-on-failure",
	},
});
