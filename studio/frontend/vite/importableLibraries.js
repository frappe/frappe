// The libraries a database app may import, as browserRuntime/importableModules.ts offers them.
// Both runtimes need this list and only one of them can load TypeScript, so it lives here and
// module-parity.cy.ts asserts the two stay in step. STUDIO_SHARED_DEPS is deliberately wider: it
// says what resolves in a build, not what an app may ask for.
export const IMPORTABLE_LIBRARIES = [
	"frappe-ui",
	"frappe-ui/charts",
	"frappe-ui/list",
	"pinia",
	"vue",
	"vue-router",
]
