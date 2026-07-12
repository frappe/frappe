const { defineConfig } = require("cypress");
const fs = require("fs");
const path = require("path");
const cypressSplit = require("cypress-split");

module.exports = defineConfig({
	projectId: "92odwv",
	adminPassword: "admin",
	testUser: "frappe@example.com",
	defaultCommandTimeout: 20000,
	pageLoadTimeout: 15000,
	video: process.env.CYPRESS_RECORD_VIDEO === "1",
	videosFolder: path.resolve(__dirname, "..", "..") + "/cypressVideos/",
	viewportHeight: 960,
	viewportWidth: 1400,
	retries: {
		runMode: 1,
		openMode: 1,
	},
	e2e: {
		// We've imported your old cypress plugins here.
		// You may want to clean this up later by importing these.
		setupNodeEvents(on, config) {
			on("before:browser:launch", (browser, launchOptions) => {
				if (browser.family === "chromium") {
					launchOptions.args.push("--disable-dev-shm-usage");
					launchOptions.args.push("--disable-gpu");
					launchOptions.args.push("--no-sandbox");
				}
				return launchOptions;
			});
			// Splitting tests only works when Cypress Cloud is not orchestrating parallel runs.
			if (process.env.CYPRESS_CLOUD_PARALLEL !== "1") {
				cypressSplit(on, config);
			}

			// Delete videos for specs where no test was retried
			// https://docs.cypress.io/guides/guides/screenshots-and-videos#Delete-videos-for-specs-without-failing-or-retried-tests
			on("after:spec", (spec, results) => {
				if (results && results.video) {
					const hadRetries = results.tests.some((test) => test.attempts.length > 1);
					if (!hadRetries) {
						fs.unlinkSync(results.video);
					}
				}
				// Write ultimately-failed spec paths to a file so CI can re-run them with video
				if (results && results.tests) {
					const lastAttemptFailed = results.tests.some(
						(test) => test.attempts[test.attempts.length - 1].state === "failed"
					);
					if (lastAttemptFailed) {
						const failedSpecsFile =
							path.resolve(__dirname, "..", "..") + "/cypress_failed_specs.txt";
						fs.appendFileSync(failedSpecsFile, spec.relative + "\n");
					}
				}
			});

			return require("./cypress/plugins/index.js")(on, config);
		},
		testIsolation: false,
		baseUrl: "http://test_site_ui:8000",
		specPattern: ["./cypress/integration/*.js", "**/ui_test_*.js"],
		excludeSpecPattern: [
			"./cypress/integration/workspace.js",
			"./cypress/integration/workspace_blocks.js",
			"./cypress/integration/customize_form.js",
		],
	},
});
