const { defineConfig } = require("cypress");
<<<<<<< HEAD
=======
const fs = require("fs");
const path = require("path");
const cypressSplit = require("cypress-split");
>>>>>>> 4c68fae18c (fix: run ui tests parallely)

module.exports = defineConfig({
	projectId: "92odwv",
	adminPassword: "admin",
	testUser: "frappe@example.com",
	defaultCommandTimeout: 20000,
	pageLoadTimeout: 15000,
	video: true,
	videoUploadOnPasses: false,
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
<<<<<<< HEAD
<<<<<<< HEAD
=======
=======
			// Splitting tests only works when Cypress Cloud is not orchestrating parallel runs.
			if (process.env.CYPRESS_CLOUD_PARALLEL !== "1") {
				cypressSplit(on, config);
			}

>>>>>>> a23b1a3624 (fix: disable cloud parallelization)
			// Delete videos for specs without failing or retried tests
			// https://docs.cypress.io/guides/guides/screenshots-and-videos#Delete-videos-for-specs-without-failing-or-retried-tests
			on("after:spec", (spec, results) => {
				if (results && results.video) {
					const failures = results.tests.some((test) =>
						test.attempts.some((attempt) => attempt.state === "failed")
					);
					if (!failures) {
						fs.unlinkSync(results.video);
					}
				}
			});

>>>>>>> 4c68fae18c (fix: run ui tests parallely)
			return require("./cypress/plugins/index.js")(on, config);
		},
		testIsolation: false,
		baseUrl: "http://test_site_ui:8000",
		specPattern: ["./cypress/integration/*.js", "**/ui_test_*.js"],
	},
});
