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

import path from "node:path";
import { fileURLToPath } from "node:url";

const SINGLETONS = ["vue", "vue-router", "frappe-ui", "reka-ui", "dompurify"];

const packageRoot = path.resolve(fileURLToPath(import.meta.url), "../..");

export default function frameworkUI(options = {}) {
	const extra = options.dedupe ?? [];
	const dedupe = [...new Set([...SINGLETONS, ...extra])];
	return [
		{
			name: "framework-ui-dedupe",
			config() {
				return {
					resolve: { dedupe },
				};
			},
		},
		resolveOwnDependencies(),
	];
}

// This package's deps (vue, frappe-ui, leaflet, …) live beside the host app: a
// bench installs node_modules there, never beside this repo's source.
function resolveOwnDependencies() {
	let hostImporter;
	return {
		name: "framework-ui-deps",
		configResolved(config) {
			hostImporter = path.join(config.root, "index.html");
		},
		// Unenforced, so vite resolves first and this only sees what the walk up
		// from this package's realpath missed. Bare specifiers only.
		async resolveId(source, importer) {
			if (!importer?.startsWith(packageRoot)) return null;
			if (/^[./]/.test(source)) return null;
			const resolved = await this.resolve(source, hostImporter);
			if (resolved || !(source in OPTIONAL_PEERS)) return resolved;
			return OPTIONAL_PREFIX + source;
		},
		load(id) {
			if (id.startsWith(OPTIONAL_PREFIX))
				return OPTIONAL_PEERS[id.slice(OPTIONAL_PREFIX.length)];
			return null;
		},
	};
}

// A peer that only the desk's own pages need. An app built on develop never installed it, and
// an unresolved import fails its whole build, so the app gets this stand-in; the code that
// imports it handles the missing value.
export const OPTIONAL_PREFIX = "\0framework-ui-optional:";
// lang-vue has a value the code checks for. lang-javascript has none to offer: its stand-in
// throws when evaluated, as frappe-ui's own language stubs do, and the editor's grammar loader
// catches that and leaves the field as plain text.
export const OPTIONAL_PEERS = {
	"@codemirror/lang-vue": "export const vueLanguage = undefined;",
	"@codemirror/lang-javascript":
		"export const javascriptLanguage = undefined;\nthrow new Error(\"Cannot find module '@codemirror/lang-javascript'\");",
};
