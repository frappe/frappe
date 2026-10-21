import path from "path"

/**
 * Resolve `@framework/ui` (the in-house `@framework/ui` package that ships raw
 * .vue/.ts source from `apps/frappe/ui`) to its source on disk.
 *
 * Studio does not install `@framework/ui` as a node dependency — it lives in a
 * sibling app (`apps/frappe/ui`). These aliases mirror the package's `exports`
 * map so studio's Vite (dev server and the per-app export build) compiles the
 * components in place. Shared singletons (vue, frappe-ui, …) imported from those
 * files are re-pointed at studio's own copies by `sharedDependencyResolver`.
 *
 * Named subpaths map to `src/components/<Name>` (or `src/utils`), so they must
 * be matched before the `./*` wildcard which would otherwise send them to
 * `src/<Name>`.
 */
const NAMED_SUBPATHS = {
	FormLayout: "components/FormLayout",
	FileUpload: "components/FileUpload",
	ListView: "components/ListView",
	SortBy: "components/SortBy",
	Filter: "components/Filter",
	QuickFilter: "components/QuickFilter",
	ColumnSettings: "components/ColumnSettings",
	fields: "components/Fields",
	utils: "utils",
}

export default function frameworkUIAlias(appsDir) {
	const src = path.resolve(appsDir, "frappe", "ui", "src")

	const named = Object.entries(NAMED_SUBPATHS).map(([subpath, target]) => ({
		find: `@framework/ui/${subpath}`,
		replacement: path.join(src, target),
	}))

	return [
		...named,
		// catch-all `@framework/ui/*` -> `src/*` (e.g. self-imports like
		// `@framework/ui/components/Link`)
		{ find: /^@framework\/ui\/(.*)$/, replacement: path.join(src, "$1") },
		// bare `@framework/ui` -> the root barrel
		{ find: /^@framework\/ui$/, replacement: path.join(src, "index.ts") },
	]
}
