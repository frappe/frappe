// Resolve app source's bare imports against the framework's ONE tree.
//
// This is the piece "the framework installs one tree under frappe/frontend/" (#42069)
// actually costs. An app's contributed files live in the app's own repo, so node
// resolution walks up from `apps/crm/...` and never reaches
// `apps/frappe/frontend/node_modules` — where the app's declared dependency was in
// fact installed, alongside the framework's own.
//
// Real node resolution from the framework's directory, not an alias table: aliasing a
// package name to a directory bypasses its `exports` map and breaks every subpath
// import, which is exactly how `frappe-ui/code-editor` failed here first time.
//
// The consequence worth naming: an app cannot import something it did not declare and
// quietly get the framework's copy — resolution is restricted to what the manifest
// says the app asked for. An undeclared import fails the build, which is the same
// answer the singleton check gives for a disagreement.

import { createRequire } from "node:module";
import { join } from "node:path";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const requireFromFrameworkTree = createRequire(join(here, "..", "package.json"));

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
			// Relative, absolute and virtual specifiers are already somebody else's.
			if (source.startsWith(".") || source.startsWith("/") || source.startsWith("\0"))
				return;
			if (source.includes(":")) return;

			const owner = apps.find(
				(entry) => entry.app !== "frappe" && importer.startsWith(entry.source_dir)
			);
			if (!owner) return;
			// A scoped package's NAME is its first two segments: '@scope/pkg'. Taking one
			// segment yields the bare scope, which is never a key in `declared`, so every
			// scoped subpath import would fall through unresolved.
			const segments = source.split("/");
			const packageName = source.startsWith("@")
				? segments.slice(0, 2).join("/")
				: segments[0];
			if (!owner.declared.has(source) && !owner.declared.has(packageName)) return;

			try {
				return requireFromFrameworkTree.resolve(source);
			} catch {
				// Fall through to vite's own resolution, so the error it reports is the
				// ordinary "failed to resolve" rather than one from in here.
				return;
			}
		},
	};
}
