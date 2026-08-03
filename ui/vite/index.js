// Vite plugin for apps that consume @framework/ui.
//
// @framework/ui ships raw .vue/.ts source and is linked into the host app by
// symlink, so the host bundler compiles it in place. Its bare imports of shared
// singletons therefore resolve by realpath into a *second* copy unless deduped,
// which breaks provide/inject context (reka-ui especially) and doubles vue.
// This plugin forces those singletons to the host's single instance.
//
// Opt-in: add `frameworkUI()` to a consuming app's vite `plugins`. Apps that do
// not use @framework/ui need not add it. Pass `{ dedupe: [...] }` to extend the
// list with app-specific raw-source singletons.
//
// Note: genuinely external deps @framework/ui owns (leaflet, vuedraggable, …)
// are NOT listed here — they ship in this package's own node_modules and resolve
// by realpath, so they must NOT be deduped to the host (the host does not have
// them). frappe-ui notably does not ship vuedraggable, so it lives in this
// package's dependencies, not the host's.

const SINGLETONS = ["vue", "vue-router", "frappe-ui", "reka-ui", "dompurify"];

export default function frameworkUI(options = {}) {
	const extra = options.dedupe ?? [];
	const dedupe = [...new Set([...SINGLETONS, ...extra])];
	return {
		name: "framework-ui-dedupe",
		config() {
			return {
				resolve: { dedupe },
			};
		},
	};
}
