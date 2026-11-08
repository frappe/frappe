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
	parseModule,
	type CompileError,
	type ModuleExports,
	type ModuleImport,
} from "@/browserRuntime/compiler"
import { loadImportableModule } from "@/browserRuntime/importableModules"

const EXTENSION_CANDIDATES = ["", ".js", ".json", "/index.js"]
const AMBIGUOUS_EXPORT = Symbol("ambiguous export")

type ModuleFactory = (exports: any, require: (specifier: string) => any, module: any) => void

export class AppCompileError extends Error {
	constructor(errors: CompileError[]) {
		super(errors.map(describeError).join("\n"))
		this.name = "AppCompileError"
	}
}

export class AppModuleRegistry {
	private files: Record<string, string>
	private factories: Record<string, ModuleFactory> = {}
	private modules = new Map<string, { exports: any }>()
	private executionErrors = new Map<string, unknown>()
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
		if (this.files[path] !== source || !this.factories[path]) {
			this.files[path] = source
			this.modules.delete(path)
			this.executionErrors.delete(path)
			delete this.failures[path]
			await this.compileInto(path, source)
			this.throwIfFailed(path)
			const errors = this.checkLocalExports(path)
			if (errors.length) this.failures[path] = errors
		}
		this.throwIfFailed(path)
	}

	hasFile(path: string): boolean {
		return this.files[path] !== undefined
	}

	private prepare(): Promise<void> {
		this.prepared ??= this.compileAll()
		return this.prepared
	}

	private async compileAll(): Promise<void> {
		for (const [path, source] of Object.entries(this.files)) {
			if (!path.endsWith(".js")) continue
			await this.compileInto(path, source)
		}
		// Every module is compiled by now, so each one's exports are known to the next check.
		for (const path of Object.keys(this.localImports)) {
			if (this.failures[path]) continue
			const errors = this.checkLocalExports(path)
			if (errors.length) this.failures[path] = errors
		}
	}

	/** Validate a file's imports, compile it and create its module factory. */
	private async compileInto(path: string, source: string): Promise<void> {
		const parsed = await parseModule(path, source, true)
		const errors = parsed.errors.length ? parsed.errors : await this.linkImports(path, parsed.imports)
		if (!errors.length) {
			const compiled = await compileFile(path, source)
			errors.push(...compiled.errors)
			if (!errors.length) {
				try {
					this.factories[path] = new Function(
						"exports",
						"require",
						"module",
						`${compiled.code}\n//# sourceURL=studio-app:///${path}`,
					) as ModuleFactory
				} catch (error) {
					// Sucrase passes through syntax only a module allows, such as top-level await.
					errors.push(importError(path, (error as Error).message))
				}
			}
			if (!errors.length) this.exports[path] = parsed.exports
		}
		if (errors.length) {
			// Drop the last working version, or a module that no longer compiles keeps running.
			delete this.factories[path]
			delete this.exports[path]
			this.failures[path] = errors
		}
	}

	/** Validate discovered imports before execution. Local paths must exist in the app.
	 * Load renderer library modules and check their requested exports. */
	private async linkImports(path: string, imports: ModuleImport[]): Promise<CompileError[]> {
		const errors: CompileError[] = []
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
				if (name === "__esModule" || !(name in namespace)) {
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
			for (const name of names) {
				const binding = this.resolveExport(specifier, name, new Set())
				if (binding === AMBIGUOUS_EXPORT) {
					errors.push(importError(path, `"${specifier}" has an ambiguous export named "${name}"`))
				} else if (binding === null) {
					errors.push(importError(path, `"${specifier}" has no export named "${name}"`))
				}
			}
		}
		return errors
	}

	/** Return a binding's origin, null if missing, an ambiguity marker, or undefined for a broken file. */
	private resolveExport(
		path: string,
		name: string,
		seen: Set<string>,
	): string | null | undefined | typeof AMBIGUOUS_EXPORT {
		const key = `${path}\0${name}`
		if (seen.has(key)) return null
		seen = new Set(seen).add(key)
		const bare = this.bare.get(path)
		if (bare) return name !== "__esModule" && name in bare ? key : null
		if (path.endsWith(".css")) return null
		if (path.endsWith(".json")) {
			const names = jsonExports(this.files[path])
			return names === null ? undefined : names.has(name) ? key : null
		}
		const own = this.exports[path]
		if (!own) return undefined
		const binding = own.bindings[name]
		if (binding) {
			if (!binding.from) return `${path}\0${binding.name}`
			const target = isLocalSpecifier(binding.from) ? this.resolve(path, binding.from) : binding.from
			if (!target) return null
			return binding.name === "*" ? `${target}\0*` : this.resolveExport(target, binding.name, seen)
		}
		if (name === "default") return null
		let found: string | null = null
		for (const specifier of own.starFrom) {
			const resolved = isLocalSpecifier(specifier) ? this.resolve(path, specifier) : specifier
			if (!resolved) return null
			const nested = this.resolveExport(resolved, name, seen)
			if (nested === undefined) return undefined
			if (nested === AMBIGUOUS_EXPORT) return AMBIGUOUS_EXPORT
			if (nested !== null) {
				if (found !== null && found !== nested) return AMBIGUOUS_EXPORT
				found = nested
			}
		}
		return found
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
		if (this.executionErrors.has(path)) throw this.executionErrors.get(path)
		const existing = this.modules.get(path)
		if (existing) return existing.exports
		const module = { exports: {} }
		this.modules.set(path, module)
		try {
			this.factories[path].call(
				undefined,
				module.exports,
				(specifier: string) => this.require(path, specifier),
				module,
			)
		} catch (error) {
			this.executionErrors.set(path, error)
			this.modules.delete(path)
			throw error
		}
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
		let element = styleElements.get(path)
		if (!element || !element.isConnected) {
			element = document.createElement("style")
			element.dataset.studioAppCss = path
			document.head.append(element)
			styleElements.set(path, element)
		}
		if (element.textContent !== this.files[path]) element.textContent = this.files[path]
		return Object.freeze(Object.defineProperty({}, "__esModule", { value: true }))
	}
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
	return Object.freeze(
		Object.defineProperty({ ...named, default: parsed }, "__esModule", { value: true, enumerable: false }),
	)
}

function importError(path: string, message: string): CompileError {
	return { file: path, line: null, column: null, message }
}

// Keep styles by file path across registry rebuilds, so edits replace styles instead of adding copies.
const styleElements = new Map<string, HTMLStyleElement>()

export function clearAppStyles(keep: Set<string> = new Set()) {
	for (const [path, element] of styleElements) {
		if (keep.has(path)) continue
		element.remove()
		styleElements.delete(path)
	}
}
