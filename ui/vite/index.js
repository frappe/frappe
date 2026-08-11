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
// list with app-specific raw-source singletons. Pass `{ extensions: true }` if
// the app hosts runtime extensions: the build then publishes shared-dep entry
// chunks and an import map (see ./extensionHost.js).

import path from "node:path";
import { fileURLToPath } from "node:url";

import extensionHost from "./extensionHost.js";

const SINGLETONS = ["vue", "vue-router", "frappe-ui", "reka-ui", "dompurify"];

const packageRoot = path.resolve(fileURLToPath(import.meta.url), "../..");
const packageSource = path.join(packageRoot, "src");

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
		...(options.extensions ? [extensionHost()] : []),
	];
}

// This package's deps (leaflet, cropperjs, …) live beside the host app: a bench
// installs node_modules there, never beside this repo's source.
function resolveOwnDependencies() {
	let hostImporter;
	return {
		name: "framework-ui-deps",
		configResolved(config) {
			hostImporter = path.join(config.root, "index.html");
		},
		// Unenforced, so vite resolves first and this only sees what the walk up
		// from this package's realpath missed. Bare specifiers only.
		resolveId(source, importer) {
			if (!importer?.startsWith(packageSource)) return null;
			if (/^[./]/.test(source)) return null;
			return this.resolve(source, hostImporter);
		},
	};
}
