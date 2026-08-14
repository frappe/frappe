import path from "path"

// reka-ui is a peerDependency of @framework/ui (like vue/vue-router/frappe-ui): a
// provide/inject singleton the host provides, not installed in the app's own
// node_modules. So @framework/ui source must resolve it to Studio's single copy —
// unlike the app's real deps (dompurify/vuedraggable/leaflet) which are installed
// under apps/frappe/ui and resolve by realpath.
// The whole @tiptap scope is here for the same reason: frappe-ui's TextEditor takes
// `extensions` built from @tiptap/core, @tiptap/pm, @tiptap/vue-3, @tiptap/extension-*
// etc., and an app has no copies of its own to build them with — nor should it, since
// an extension made from a second copy never registers against the editor's schema.
const STUDIO_SHARED_DEPS = ["vue", "vue-router", "pinia", "frappe-ui", "reka-ui", "@tiptap"]
/**
 * Vite plugin to redirect shared dependency imports from files outside the Studio
 * project (custom Vue components and @framework/ui source) to Studio's own
 * installations.
 *
 * These are singleton deps (vue, vue-router, frappe-ui, reka-ui, @tiptap/*) that must
 * resolve from Studio to avoid duplicate instances. App-specific deps (including
 * @framework/ui's own dompurify/vuedraggable/leaflet) resolve normally from the
 * app's own node_modules.
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
