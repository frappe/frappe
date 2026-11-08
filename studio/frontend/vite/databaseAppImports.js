import fs from "node:fs"
import path from "node:path"
import { babelParse } from "vue/compiler-sfc"
import { IMPORTABLE_MODULES } from "../src/browserRuntime/importableLibraries.js"
import { moduleSyntaxErrors } from "../src/browserRuntime/moduleContract.js"

const CSS_PREFIX = "\0studio-database-css:"

/** Restrict database source without restricting the renderer or its libraries. */
export default function databaseAppImports(appFolder) {
	const root = fs.realpathSync(appFolder) + path.sep
	const inApp = (id) => {
		const file = id.split("?")[0]
		return path.isAbsolute(file) && fs.existsSync(file) && fs.realpathSync(file).startsWith(root)
	}
	const getModuleId = (file) => (file.endsWith(".css") ? CSS_PREFIX + file + ".js" : file)

	return {
		name: "studio-database-app-imports",
		enforce: "pre",
		transform(source, id) {
			if (!inApp(id) || !id.endsWith(".js")) return
			const { program } = babelParse(source, { sourceType: "module" })
			const errors = moduleSyntaxErrors(program, path.relative(root, id))
			if (errors.length)
				this.error(errors.map((error) => `${error.file}:${error.line}: ${error.message}`).join("\n"))
		},
		async resolveId(source, importer, options) {
			// App metadata must not redirect a generated renderer's entry outside the app.
			if (path.isAbsolute(source) && inApp(source) && fs.statSync(source).isFile()) {
				return getModuleId(fs.realpathSync(source))
			}
			if (!importer || source.startsWith("\0") || !inApp(importer)) return null
			if (IMPORTABLE_MODULES.includes(source)) return null
			if (!source.startsWith(".") && !source.startsWith("@app/") && !path.isAbsolute(source)) {
				this.error(`"${source}" is not importable in a database app.`)
			}
			const resolved = await this.resolve(source, importer, { ...options, skipSelf: true })
			if (!resolved || !path.isAbsolute(resolved.id)) return resolved
			if (!inApp(resolved.id)) this.error(`"${source}" resolves outside the app.`)
			return resolved.id.endsWith(".css") ? getModuleId(resolved.id) : resolved
		},
		load(id) {
			if (!id.startsWith(CSS_PREFIX)) return
			const file = id.slice(CSS_PREFIX.length, -3)
			if (!inApp(file)) this.error(`"${file}" resolves outside the app.`)
			const css = fs.readFileSync(file, "utf8")
			// Match the preview: CSS URLs resolve in the browser, never against the server filesystem.
			return `const style = document.createElement("style")
style.dataset.studioAppCss = ${JSON.stringify(path.relative(root, file))}
style.textContent = ${JSON.stringify(css)}
document.head.append(style)`
		},
	}
}
