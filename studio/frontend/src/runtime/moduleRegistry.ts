/**
 * Links and runs a database app's compiled modules. Each module executes once as CommonJS inside
 * a registry, so an import cycle resolves the way it does in a bundler, and `.css` imports inject
 * styles. Bare imports come from the renderer's own modules (importableModules.ts).
 *
 * Resolution mirrors what a real Vite build resolves — `@app/` maps to the app root (the
 * studioRootAlias plugin), relative paths try Vite's default extensions, and `.vue` or `.css`
 * need an explicit extension — so an import that works here keeps working once the app's files
 * move to a repository.
 */

import { compileFile, describeError, parseImports, toCommonJS, type CompileError } from "@/runtime/compiler"
import { loadImportableModule } from "@/runtime/importableModules"

const EXTENSION_CANDIDATES = ["", ".ts", ".js", ".json", "/index.ts", "/index.js"]

type ModuleFactory = (exports: any, require: (specifier: string) => any, module: any) => void

export class AppCompileError extends Error {
	errors: CompileError[]

	constructor(errors: CompileError[]) {
		super(errors.map(describeError).join("\n"))
		this.name = "AppCompileError"
		this.errors = errors
	}
}

export class AppModuleRegistry {
	private files: Record<string, string>
	private factories: Record<string, ModuleFactory> = {}
	private styles: Record<string, string> = {}
	private modules = new Map<string, { exports: any }>()
	private bare = new Map<string, any>()
	private prepared: Promise<void> | null = null

	constructor(files: Record<string, string>) {
		this.files = { ...files }
	}

	/** Load a module by its exact path in the app (e.g. "router.ts", "components/Card.vue"). */
	async loadModule(path: string): Promise<any> {
		await this.prepare()
		if (!this.factories[path]) throw new Error(`${path} is not a module in this app.`)
		return this.load(path)
	}

	/** Add or replace one file after boot (a page script mounted at its virtual path) and keep
	 * every already-executed module as it is. */
	async addFile(path: string, source: string): Promise<void> {
		await this.prepare()
		if (this.files[path] === source && this.factories[path]) return
		this.files[path] = source
		this.modules.delete(path)
		await this.compileInto(path, source)
		applyStyles(this.styles)
	}

	hasFile(path: string): boolean {
		return this.files[path] !== undefined
	}

	private prepare(): Promise<void> {
		this.prepared ??= this.compileAll()
		return this.prepared
	}

	private async compileAll(): Promise<void> {
		const errors: CompileError[] = []
		for (const [path, source] of Object.entries(this.files)) {
			if (!isCompiledModule(path)) continue
			errors.push(...(await this.compileInto(path, source, false)))
		}
		if (errors.length) throw new AppCompileError(errors)
		applyStyles(this.styles)
	}

	/** Compile one file, link-check its imports, and register its factory. */
	private async compileInto(path: string, source: string, throwOnError = true): Promise<CompileError[]> {
		const compiled = await compileFile(path, source)
		const errors = [...compiled.errors]
		if (!errors.length) {
			errors.push(...(await this.linkImports(path, compiled.code)))
		}
		if (!errors.length) {
			const commonjs = await toCommonJS(path, compiled.code)
			errors.push(...commonjs.errors)
			if (!errors.length) {
				this.factories[path] = new Function(
					"exports",
					"require",
					"module",
					`${commonjs.code}\n//# sourceURL=studio-app:///${path}`,
				) as ModuleFactory
				if (compiled.css) this.styles[path] = compiled.css
			}
		}
		if (errors.length && throwOnError) throw new AppCompileError(errors)
		return errors
	}

	/** Resolve every import up front: bare ones load from the renderer's modules, relative ones
	 * must exist in the app, and named imports from bare modules must actually be exported. */
	private async linkImports(path: string, code: string): Promise<CompileError[]> {
		const { imports, errors } = await parseImports(path, code)
		if (errors.length) return errors

		for (const { specifier, names } of imports) {
			if (isLocalSpecifier(specifier)) {
				if (!this.resolve(path, specifier)) {
					errors.push(importError(path, `Cannot resolve "${specifier}"`))
				}
				continue
			}
			if (!this.bare.has(specifier)) {
				try {
					this.bare.set(specifier, await loadImportableModule(specifier))
				} catch (error: any) {
					errors.push(importError(path, error?.message || String(error)))
					continue
				}
			}
			const namespace = this.bare.get(specifier)
			for (const name of names) {
				if (!(name in namespace)) {
					errors.push(importError(path, `"${specifier}" has no export named "${name}"`))
				}
			}
		}
		return errors
	}

	private require(from: string, specifier: string): any {
		if (!isLocalSpecifier(specifier)) {
			const namespace = this.bare.get(specifier)
			if (!namespace) throw new Error(`Cannot resolve "${specifier}" from ${from}`)
			return namespace
		}
		const resolved = this.resolve(from, specifier)
		if (!resolved) throw new Error(`Cannot resolve "${specifier}" from ${from}`)
		if (resolved.endsWith(".css")) return this.injectCSS(resolved)
		if (resolved.endsWith(".json") && !this.factories[resolved]) return parseJSONModule(this.files[resolved])
		if (!this.factories[resolved]) throw new Error(`Cannot import "${specifier}" from ${from}: not a module`)
		return this.load(resolved)
	}

	/** Each module runs once into its own exports object, registered before the body runs, so an
	 * import cycle sees the partly filled exports. */
	private load(path: string): any {
		const existing = this.modules.get(path)
		if (existing) return existing.exports
		const module = { exports: {} }
		this.modules.set(path, module)
		this.factories[path](module.exports, (specifier: string) => this.require(path, specifier), module)
		return module.exports
	}

	private resolve(from: string, specifier: string): string | null {
		const base = specifier.startsWith("@app/")
			? specifier.slice("@app/".length)
			: joinRelative(from, specifier)
		if (base === null) return null
		if (base.endsWith(".vue") || base.endsWith(".css")) {
			return this.files[base] !== undefined ? base : null
		}
		for (const extension of EXTENSION_CANDIDATES) {
			if (this.files[base + extension] !== undefined) return base + extension
		}
		return null
	}

	private injectCSS(path: string): any {
		this.styles[path] = this.files[path]
		applyStyles(this.styles)
		return Object.freeze({ __esModule: true, default: path })
	}
}

function isCompiledModule(path: string): boolean {
	return path.endsWith(".vue") || path.endsWith(".ts") || path.endsWith(".js")
}

function isLocalSpecifier(specifier: string): boolean {
	return specifier.startsWith(".") || specifier.startsWith("@app/")
}

/** "pages/a/a.ts" + "../../utils/x" -> "utils/x"; null when the path escapes the app root. */
function joinRelative(from: string, specifier: string): string | null {
	const parts = from.split("/").slice(0, -1)
	for (const segment of specifier.split("/")) {
		if (segment === "." || segment === "") continue
		if (segment === "..") {
			if (!parts.length) return null
			parts.pop()
		} else {
			parts.push(segment)
		}
	}
	return parts.join("/")
}

function parseJSONModule(source: string): any {
	const parsed = JSON.parse(source)
	return Object.freeze({ __esModule: true, default: parsed })
}

function importError(path: string, message: string): CompileError {
	return { file: path, line: null, column: null, message }
}

// Styles are keyed by file path in the document head, shared across runtime rebuilds so a
// rebuild replaces a file's styles instead of stacking duplicates.
const styleElements = new Map<string, HTMLStyleElement>()

function applyStyles(styles: Record<string, string>) {
	for (const [path, css] of Object.entries(styles)) {
		let element = styleElements.get(path)
		if (!element || !element.isConnected) {
			element = document.createElement("style")
			element.dataset.studioAppCss = path
			document.head.append(element)
			styleElements.set(path, element)
		}
		if (element.textContent !== css) element.textContent = css
	}
}

export function clearAppStyles(keep: Set<string> = new Set()) {
	for (const [path, element] of styleElements) {
		if (keep.has(path)) continue
		element.remove()
		styleElements.delete(path)
	}
}
