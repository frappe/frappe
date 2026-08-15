import { defineConfig } from "cypress"

export default defineConfig({
	allowCypressEnv: false,
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

