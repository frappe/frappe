import fs from "fs"
import path from "path"
import { IMPORTABLE_LIBRARIES } from "./importableLibraries.js"

/**
 * Hold a database app's build to the import contract its preview already enforces.
 *
 * The preview resolves an app's imports against its own file map, so a path outside the app
 * cannot resolve at all. A build resolves against the filesystem, where it can, and would inline
 * whatever file it reaches into a bundle the app serves. `@app/` is only a prefix: path.join
 * normalises `..`, so `@app/../..` leaves the app folder.
 *
 * Repository apps are exempt. Their files are written by developers who already have server
 * access, and they import node_modules, @framework/ui and Studio's own source.
 */
const APP_PREFIX = "@app/"

export default function databaseAppImports(appFolder) {
	// Compare real paths: the build folder is under a symlink on macOS, and a bench can be one too.
	const root = realPath(appFolder) + path.sep
	const inApp = (file) => realPath(path.resolve(file.split("?")[0])).startsWith(root)

	return {
		name: "studio-database-app-imports",
		enforce: "pre", // see the specifier before studioRootAlias rewrites it

		async resolveId(source, importer, options) {
			// Only the app's own files are held to the contract. The generated renderer, Studio's
			// source and a library's own dependencies resolve as they always do. A virtual id, such
			// as the preload helper Vite adds to a dynamic import, names no file to contain.
			if (!importer || source.startsWith("\0") || !inApp(importer)) return null

			const specifier = source.split("?")[0]
			if (!specifier.startsWith(".") && !specifier.startsWith("/") && !specifier.startsWith(APP_PREFIX)) {
				if (!IMPORTABLE_LIBRARIES.includes(specifier)) {
					this.error(
						`"${source}" is not importable in a database app. ` +
							`It can import ${IMPORTABLE_LIBRARIES.join(", ")}, and its own files.`,
					)
				}
				return null
			}

			// `@app/` already means the app root, so it never needs to walk up from there.
			if (specifier.startsWith(APP_PREFIX) && specifier.split("/").includes("..")) {
				this.error(`"${source}" must not walk above the app root.`)
			}

			const resolved = await this.resolve(source, importer, { ...options, skipSelf: true })
			// A virtual id from another plugin names no file, so there is nothing to contain.
			if (resolved && isFilePath(resolved.id) && !inApp(resolved.id)) {
				this.error(`"${source}" resolves outside the app.`)
			}
			return resolved
		},
	}
}

function isFilePath(id) {
	return !id.startsWith("\0") && path.isAbsolute(id.split("?")[0])
}

function realPath(file) {
	try {
		return fs.realpathSync(file)
	} catch {
		return path.resolve(file)
	}
}
