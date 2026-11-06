/**
 * Link and execute a database app's compiled modules as CommonJS.
 * Execute each module once and cache its exports. CSS imports add styles to the document;
 * library imports reuse the renderer's modules from importableModules.ts.
 *
 * The Blob-based native ESM experiment could reuse the renderer's Vue instance, but the browser
 * retained evaluated module revisions for the document's lifetime. This registry and its cache
 * can be collected when they are no longer referenced. See branch codex/native-esm-prototype.
 *
 * Use the app build's path rules: @app/ points to the app root, relative paths try supported
 * extensions and index files, and a .css import needs its explicit extension.
 */

import {
	compileFile,
	describeError,
	parseExports,
	parseImports,
	type CompileError,
	type ModuleExports,
	type ModuleImport,
} from "@/browserRuntime/compiler"
import { loadImportableModule } from "@/browserRuntime/importableModules"

const EXTENSION_CANDIDATES = ["", ".js", ".json", "/index.js"]

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
	private failures: Record<string, CompileError[]> = {}
	private exports: Record<string, ModuleExports> = {}
	private localImports: Record<string, ModuleImport[]> = {}
	private bare = new Map<string, any>()
	private prepared: Promise<void> | null = null

	constructor(files: Record<string, string>) {
		this.files = { ...files }
	}

	/** Load a module by its exact path relative to the app root, such as stores/catalog.js. */
	async loadModule(path: string): Promise<any> {
		await this.prepare()
		this.throwIfFailed(path)
		if (!this.factories[path]) throw new Error(`${path} is not a module in this app.`)
		return this.load(path)
	}

	/** Add or replace a file and clear only that module's cached exports.
	 * Other module caches stay unchanged, so cached importers may still hold older exports. */
	async addFile(path: string, source: string): Promise<void> {
		await this.prepare()
		if (this.files[path] === source && this.factories[path]) return
		this.files[path] = source
		this.modules.delete(path)
		delete this.failures[path]
		await this.compileInto(path, source)
		const errors = this.checkLocalExports(path)
		if (errors.length) throw new AppCompileError(errors)
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
		this.failures = {}
		this.exports = {}
		this.localImports = {}
		for (const [path, source] of Object.entries(this.files)) {
			if (!isCompiledModule(path)) continue
			const errors = await this.compileInto(path, source, false)
			if (errors.length) this.failures[path] = errors
		}
		// Every module is compiled by now, so each one's exports are known to the next check.
		for (const path of Object.keys(this.localImports)) {
			if (this.failures[path]) continue
			const errors = this.checkLocalExports(path)
			if (errors.length) this.failures[path] = errors
		}
		applyStyles(this.styles)
	}

	/** Validate a file's imports, compile it and create its module factory. */
	private async compileInto(path: string, source: string, throwOnError = true): Promise<CompileError[]> {
		const errors = await this.linkImports(path, source)
		if (!errors.length) {
			const compiled = await compileFile(path, source)
			errors.push(...compiled.errors)
			if (!errors.length) {
				this.factories[path] = new Function(
					"exports",
					"require",
					"module",
					`${compiled.code}\n//# sourceURL=studio-app:///${path}`,
				) as ModuleFactory
				const parsed = await parseExports(path, source)
				if (!parsed.errors.length) this.exports[path] = parsed.exports
			}
		}
		if (errors.length && throwOnError) throw new AppCompileError(errors)
		return errors
	}

	/** Validate discovered imports before execution. Local paths must exist in the app.
	 * Load renderer library modules and check their requested named exports. */
	private async linkImports(path: string, code: string): Promise<CompileError[]> {
		const { imports, errors } = await parseImports(path, code)
		if (errors.length) return errors

		this.localImports[path] = []
		for (const { specifier, names } of imports) {
			if (isLocalSpecifier(specifier)) {
				const resolved = this.resolve(path, specifier)
				if (!resolved) {
					errors.push(importError(path, `Cannot resolve "${specifier}"`))
				} else if (names.length) {
					this.localImports[path].push({ specifier: resolved, names })
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

	/** Check what this file imports from the app's own modules against what they export. */
	private checkLocalExports(path: string): CompileError[] {
		const errors: CompileError[] = []
		for (const { specifier, names } of this.localImports[path] || []) {
			const available = this.exportsOf(specifier, new Set())
			if (!available) continue
			for (const name of names) {
				if (!available.has(name)) {
					errors.push(importError(path, `"${specifier}" has no export named "${name}"`))
				}
			}
		}
		return errors
	}

	/** The names a file exports, or null when they cannot be known without running it. Returning
	 * null skips the check, because a wrong error here would break a working app. */
	private exportsOf(path: string, seen: Set<string>): Set<string> | null {
		if (seen.has(path)) return new Set()
		seen.add(path)
		if (path.endsWith(".css")) return new Set(["default"])
		if (path.endsWith(".json")) return jsonExports(this.files[path])
		const own = this.exports[path]
		if (!own) return null
		const names = new Set(own.names)
		for (const specifier of own.starFrom) {
			const resolved = isLocalSpecifier(specifier) ? this.resolve(path, specifier) : null
			if (!resolved) return null
			const nested = this.exportsOf(resolved, seen)
			if (!nested) return null
			for (const name of nested) if (name !== "default") names.add(name)
		}
		return names
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
		this.throwIfFailed(resolved)
		if (!this.factories[resolved]) throw new Error(`Cannot import "${specifier}" from ${from}: not a module`)
		return this.load(resolved)
	}

	/** A file that does not compile fails the modules that import it, not every other page. */
	private throwIfFailed(path: string) {
		if (this.failures[path]) throw new AppCompileError(this.failures[path])
	}

	/** Cache the exports object before execution so cycles can read partially initialized exports. */
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
		if (base.endsWith(".css")) {
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
	return path.endsWith(".js")
}

function isLocalSpecifier(specifier: string): boolean {
	return specifier.startsWith(".") || specifier.startsWith("@app/")
}

/** Resolve a relative import from its file's directory. Return null if it escapes the app root. */
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

function jsonExports(source: string): Set<string> | null {
	try {
		const parsed = JSON.parse(source)
		const keys = parsed && typeof parsed === "object" && !Array.isArray(parsed) ? Object.keys(parsed) : []
		return new Set([...keys, "default"])
	} catch {
		return null
	}
}

function parseJSONModule(source: string): any {
	const parsed = JSON.parse(source)
	// Vite turns a JSON object's top-level keys into named exports. Offer the same names here, so
	// an app that imports them keeps working after its files move to a repository.
	const named = parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {}
	return Object.freeze({ ...named, __esModule: true, default: parsed })
}

function importError(path: string, message: string): CompileError {
	return { file: path, line: null, column: null, message }
}

// Keep styles by file path across registry rebuilds, so edits replace styles instead of adding copies.
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
