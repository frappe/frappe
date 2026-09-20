/**
 * Temporary: frappe-ui's `frappeui-code-languages` plugin stubs the optional
 * `@codemirror/lang-*` packages during dependency pre-bundling through an esbuild
 * plugin. Vite 8 pre-bundles with Rolldown, whose esbuild shim has no
 * `build.resolve`, so the twin throws "Not implemented", the dependency scan fails
 * and pre-bundling is skipped entirely. Dependencies are then discovered mid-run and
 * the page reloads under whatever is on screen — in CI that reload lands inside a
 * component test and fails it.
 *
 * Dropping the twin lets the scan run. Its own `resolveId` hook still stubs an
 * absent language for the module graph. Remove this once frappe-ui contributes the
 * plugin through `optimizeDeps.rolldownOptions` instead.
 */
export default function frappeUICodeLanguagesFix() {
	return {
		name: "studio:frappe-ui-code-languages-fix",
		enforce: "post",
		configResolved(config) {
			const plugins = config.optimizeDeps?.esbuildOptions?.plugins
			if (!plugins) return
			config.optimizeDeps.esbuildOptions.plugins = plugins.filter(
				(plugin) => plugin.name !== "frappeui-code-languages",
			)
		},
	}
}
