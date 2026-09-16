// Resolve an app's bare imports from the framework's tree, which node resolution walking up
// from the app's own repo never reaches. Only what the app declared resolves; nothing is aliased.

import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const requireFromFrameworkTree = createRequire(join(here, "..", "package.json"));

// `preserveSymlinks` keeps the linked `@framework/ui` under node_modules, so a relative
// import that climbs out of the package lands in node_modules; resolve it from the real tree.
export const LINKED_UI = join(here, "..", "node_modules", "@framework", "ui");
export const REAL_UI = join(here, "..", "..", "ui");

export default function oneTree(manifest) {
	// Which app owns which source tree, so an importer can be attributed.
	const apps = manifest.map(({ app, source_dir, runtime_deps }) => ({
		app,
		source_dir,
		declared: new Set(Object.keys(runtime_deps ?? {})),
	}));

	return {
		name: "frappe-one-tree",
		resolveId(source, importer) {
			if (!importer) return;
			if (source.startsWith("../")) return outOfLinkedPackage(source, importer);
			// Relative, absolute and virtual specifiers are already somebody else's.
			if (source.startsWith(".") || source.startsWith("/") || source.startsWith("\0"))
				return;
			if (source.includes(":")) return;

			const owner = apps.find(
				(entry) => entry.app !== "frappe" && importer.startsWith(entry.source_dir)
			);
			if (!owner) return;
			// A scoped package's name is its first two segments, '@scope/pkg'.
			const segments = source.split("/");
			const packageName = source.startsWith("@")
				? segments.slice(0, 2).join("/")
				: segments[0];
			if (!owner.declared.has(source) && !owner.declared.has(packageName)) return;

			try {
				return requireFromFrameworkTree.resolve(source);
			} catch {
				// Fall through so vite reports the ordinary "failed to resolve".
				return;
			}
		},
	};
}

export function outOfLinkedPackage(source, importer, linked = LINKED_UI, real = REAL_UI) {
	if (!importer.startsWith(linked + "/")) return;
	const target = resolve(dirname(importer), source);
	if (target.startsWith(linked + "/")) return;
	const realTarget = resolve(dirname(real + importer.slice(linked.length)), source);
	return existsSync(realTarget) ? realTarget : undefined;
}
