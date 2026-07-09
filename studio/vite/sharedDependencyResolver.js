import path from "path"

// reka-ui and dompurify are the extra singletons @framework/ui declares (see its
// `./vite` dedupe plugin): its source is compiled in place from apps/frappe/ui, so
// these must resolve to Studio's single copy too, not the sibling app's node_modules.
const STUDIO_SHARED_DEPS = ["vue", "vue-router", "pinia", "frappe-ui", "reka-ui", "dompurify"]
/**
 * Vite plugin to redirect shared dependency imports from files outside the Studio
 * project (custom Vue components and @framework/ui source) to Studio's own
 * installations.
 *
 * These are singleton deps (vue, vue-router, frappe-ui, reka-ui, dompurify) that
 * must resolve from Studio to avoid duplicate instances. App-specific deps
 * resolve normally from the app's own node_modules.
 */
function sharedDependencyResolver(STUDIO_ROOT) {
	return {
		name: "shared-dependency-resolver",
		enforce: "pre",
		async resolveId(source, importer, options) {
			// Only intercept shared deps
			if (!STUDIO_SHARED_DEPS.some((dep) => source === dep || source.startsWith(dep + "/"))) return null
			// Only intercept if the importer is outside Studio's project
			if (!importer || importer.startsWith(STUDIO_ROOT)) return null

			// Re-resolve from Studio's project root so Vite finds the right copy
			const resolved = await this.resolve(source, path.join(STUDIO_ROOT, "frontend", "_virtual.js"), {
				...options,
				skipSelf: true,
			})
			return resolved
		},
	}
}

export default sharedDependencyResolver
