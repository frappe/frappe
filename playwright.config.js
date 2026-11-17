const { defineConfig } = require("@playwright/test");
const { WORKERS } = require("./playwright/support/config");

const ci = Boolean(process.env.CI);

module.exports = defineConfig({
	testDir: "./playwright/tests",
	fullyParallel: false,
	workers: WORKERS,
	forbidOnly: ci,
	retries: 1,
	timeout: 120000,
	expect: { timeout: 20000 },
	reporter: ci ? [["list"], ["github"], ["html", { open: "never" }]] : [["list"]],
	use: {
		viewport: { width: 1400, height: 960 },
		actionTimeout: 20000,
		navigationTimeout: 30000,
		trace: "on-first-retry",
		screenshot: "only-on-failure",
	},
});
