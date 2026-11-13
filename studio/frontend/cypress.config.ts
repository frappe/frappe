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
			viteConfig: {
				configFile: "vite.config.js",
				// a separate dep cache, so running specs never re-optimizes the one a live `yarn dev` is serving
				cacheDir: "node_modules/.vite-cypress",
				// frappe-ui is excluded from the pre-bundle, so the start-up scan misses the deps of its
				// lazily loaded editor; found mid-run, they re-optimize deps and fail the spec loading then
				optimizeDeps: {
					include: [
						"@tiptap/extension-blockquote",
						"@tiptap/extension-bold",
						"@tiptap/extension-document",
						"@tiptap/extension-hard-break",
						"@tiptap/extension-horizontal-rule",
						"@tiptap/extension-italic",
						"@tiptap/extension-paragraph",
						"@tiptap/extension-placeholder",
						"@tiptap/extension-strike",
						"@tiptap/extension-task-item",
						"@tiptap/extension-task-list",
						"@tiptap/extension-text",
						"@tiptap/extension-underline",
						"@tiptap/markdown",
						"@tiptap/pm/history",
						"@tiptap/pm/tables",
						"@tiptap/pm/transform",
					],
				},
			},
		},
		specPattern: "cypress/component/**/*.cy.ts",
		supportFile: "cypress/support/component.ts",
	},
})
