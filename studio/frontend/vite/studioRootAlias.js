import path from "path"

/**
 * Import alias for files under an exported app's `studio/<studio_app>/` folder:
 * `@app/x` resolves to `<frappe_app>/studio/<studio_app>/x`, so page scripts, components and
 * composables can import each other from the studio-app root instead of walking `../../` paths.
 *
 * The target is computed per importer — each studio app is its own root — so this can't be a static
 * Vite alias. Runs in both the dev server (vite.config.js) and the per-app build (scripts/build.js).
 */
const PREFIX = "@app/"
const STUDIO_SEGMENT = "/studio/"

export default function studioRootAlias() {
	return {
		name: "studio-root-alias",
		enforce: "pre", // resolve @app/ before Vite's own alias/resolve plugins

		async resolveId(source, importer) {
			if (!importer || !source.startsWith(PREFIX)) return null
			const root = studioAppRoot(importer)
			if (!root) return null
			const target = path.join(root, source.slice(PREFIX.length))
			// delegate to the normal resolver so extensions (.ts/.js/.vue) and index files resolve
			const resolved = await this.resolve(target, importer, { skipSelf: true })
			return resolved?.id ?? null
		},
	}
}

// ".../<frappe_app>/studio/<studio_app>/..." -> ".../<frappe_app>/studio/<studio_app>"
function studioAppRoot(importer) {
	let file = importer.split("?")[0].replace(/\\/g, "/")
	// the dev server prefixes files outside its root with /@fs/ — strip it to get the real fs path
	if (file.startsWith("/@fs/")) file = file.slice("/@fs".length)
	const index = file.indexOf(STUDIO_SEGMENT)
	if (index === -1) return null
	const studioApp = file.slice(index + STUDIO_SEGMENT.length).split("/")[0]
	if (!studioApp) return null
	return file.slice(0, index + STUDIO_SEGMENT.length) + studioApp
}
