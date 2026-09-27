import { defineConfig } from "cypress"

export default defineConfig({
	allowCypressEnv: false,
	// Site and Administrator password the server-backed specs log in with (the CI site's defaults).
	// Override locally: CYPRESS_adminPassword=<password> yarn test:cypress --expose site=<site>
	expose: { site: "test_site" },
	env: { adminPassword: "admin" },
	component: {
		// Reuses the app's vite.config.js (provides the "@" alias, frappe-ui plugin & lucide icons)
		devServer: {
			framework: "vue",
			bundler: "vite",
		},
		specPattern: "cypress/component/**/*.cy.ts",
		supportFile: "cypress/support/component.ts",
	},
})
