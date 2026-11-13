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
import { injectAppStyle } from "@/browserRuntime/appStyles"
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

/** The state of one .js file. A new version of the file gets a new record. */
interface ModuleRecord {
	factory?: ModuleFactory
	/** The names that the file exports. Not set if the file did not compile. */
	exportNames?: ModuleExports
	/** The names that the file imports from the app's own modules. */
	appImports: ModuleImport[]
	/** The reasons why the file cannot run. */
	errors?: CompileError[]
	/** The exports object, set when execution starts. */
	exports?: any
	/** The value that the file threw during execution. The key is not set if it did not throw. */
	runtimeError?: unknown
}

export class AppModuleRegistry {
	private files: Record<string, string>
	private records = new Map<string, ModuleRecord>()
	private libraries = new Map<string, any>()
	private compiled: Promise<void> | null = null

	constructor(files: Record<string, string>) {
		this.files = { ...files }
	}

	/** Load a module by its exact path relative to the app root, such as stores/catalog.js. */
	async loadModule(path: string): Promise<any> {
		await (this.compiled ??= this.compileAll())
		return this.load(path, `${path} is not a module in this app.`)
	}

	/** Add or replace a file and clear only that module's cached exports.
	 * Other module caches stay unchanged, so cached importers may still hold older exports. */
	async addFile(path: string, source: string): Promise<void> {
		await (this.compiled ??= this.compileAll())
		let record = this.records.get(path)
		if (this.files[path] !== source || !record?.factory) {
			this.files[path] = source
			record = await this.compile(path, source)
			this.records.set(path, record)
			if (!record.errors) this.checkAppImports(path, record)
		}
		if (record.errors) throw new AppCompileError(record.errors)
	}

	hasFile(path: string): boolean {
		return this.files[path] !== undefined
	}

	private async compileAll(): Promise<void> {
		for (const [path, source] of Object.entries(this.files)) {
			if (path.endsWith(".js")) this.records.set(path, await this.compile(path, source))
		}
		// Every module is compiled by now, so each one's exports are known to the next check.
		for (const [path, record] of this.records) {
			if (!record.errors) this.checkAppImports(path, record)
		}
	}

	/** Validate a file's imports, compile it and create its module factory. */
	private async compile(path: string, source: string): Promise<ModuleRecord> {
		const record: ModuleRecord = { appImports: [] }
		const parsed = await parseModule(path, source, true)
		const errors = parsed.errors.length
			? parsed.errors
			: await this.linkImports(path, parsed.imports, record.appImports)
		if (!errors.length) {
			const compiled = await compileFile(path, source)
			errors.push(...compiled.errors)
			if (!errors.length) {
				try {
					record.factory = new Function(
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
		}
		if (errors.length) record.errors = errors
		else record.exportNames = parsed.exports
		return record
	}

	/** Validate discovered imports before execution. An app path must name a file of the app, and its
	 * named imports go into `appImports`. Load renderer library modules and check their
	 * requested exports. */
	private async linkImports(
		path: string,
		imports: ModuleImport[],
		appImports: ModuleImport[],
	): Promise<CompileError[]> {
		const errors: CompileError[] = []
		for (const { specifier, names } of imports) {
			if (isAppSpecifier(specifier)) {
				const resolved = this.resolve(path, specifier)
				if (!resolved) {
					errors.push(importError(path, `Cannot resolve "${specifier}"`))
				} else if (names.length) {
					appImports.push({ specifier: resolved, names })
				}
				continue
			}
			if (!this.libraries.has(specifier)) {
				try {
					this.libraries.set(specifier, await loadImportableModule(specifier))
				} catch (error: any) {
					errors.push(importError(path, error?.message || String(error)))
					continue
				}
			}
			const namespace = this.libraries.get(specifier)
			for (const name of names) {
				if (name === "__esModule" || !(name in namespace)) {
					errors.push(importError(path, `"${specifier}" has no export named "${name}"`))
				}
			}
		}
		return errors
	}

	/** Check what this file imports from the app's own modules against what they export. */
	private checkAppImports(path: string, record: ModuleRecord) {
		const errors: CompileError[] = []
		for (const { specifier, names } of record.appImports) {
			for (const name of names) {
				const binding = this.resolveExport(specifier, name, new Set())
				if (binding === AMBIGUOUS_EXPORT) {
					errors.push(importError(path, `"${specifier}" has an ambiguous export named "${name}"`))
				} else if (binding === null) {
					errors.push(importError(path, `"${specifier}" has no export named "${name}"`))
				}
			}
		}
		if (errors.length) record.errors = errors
	}

	/** Follow re-exports to their original binding: two paths to the same binding are not ambiguous.
	 * Return null if missing, an ambiguity marker for competing bindings, or undefined for a broken file. */
	private resolveExport(
		path: string,
		name: string,
		seen: Set<string>,
	): string | null | undefined | typeof AMBIGUOUS_EXPORT {
		const key = `${path}\0${name}`
		if (seen.has(key)) return null
		seen = new Set(seen).add(key)
		const library = this.libraries.get(path)
		if (library) return name !== "__esModule" && name in library ? key : null
		if (path.endsWith(".css")) return null
		if (path.endsWith(".json")) {
			const names = jsonExports(this.files[path])
			return names === null ? undefined : names.has(name) ? key : null
		}
		const own = this.records.get(path)?.exportNames
		if (!own) return undefined
		const binding = own.bindings[name]
		if (binding) {
			if (!binding.from) return `${path}\0${binding.name}`
			const target = isAppSpecifier(binding.from) ? this.resolve(path, binding.from) : binding.from
			if (!target) return null
			return binding.name === "*" ? `${target}\0*` : this.resolveExport(target, binding.name, seen)
		}
		if (name === "default") return null
		let found: string | null = null
		for (const specifier of own.starFrom) {
			const resolved = isAppSpecifier(specifier) ? this.resolve(path, specifier) : specifier
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
		if (!isAppSpecifier(specifier)) {
			const namespace = this.libraries.get(specifier)
			if (!namespace) throw new Error(`Cannot resolve "${specifier}" from ${from}`)
			return namespace
		}
		const resolved = this.resolve(from, specifier)
		if (!resolved) throw new Error(`Cannot resolve "${specifier}" from ${from}`)
		if (resolved.endsWith(".css")) {
			injectAppStyle(resolved, this.files[resolved])
			return Object.freeze(Object.defineProperty({}, "__esModule", { value: true }))
		}
		if (resolved.endsWith(".json")) return parseJSONModule(this.files[resolved])
		return this.load(resolved, `Cannot import "${specifier}" from ${from}: not a module`)
	}

	/** Execute a module once and return its exports. Cache the exports object before execution
	 * so cycles can read partially initialized exports. */
	private load(path: string, notAModule: string): any {
		const record = this.records.get(path)
		// A file that does not compile fails the modules that import it, not every other page.
		if (record?.errors) throw new AppCompileError(record.errors)
		if (!record?.factory) throw new Error(notAModule)
		// A module may throw after side effects; revisiting it must not execute those effects again.
		if ("runtimeError" in record) throw record.runtimeError
		if (record.exports) return record.exports
		const exports = (record.exports = {})
		try {
			record.factory.call(undefined, exports, (specifier: string) => this.require(path, specifier), {
				exports,
			})
		} catch (error) {
			record.runtimeError = error
			throw error
		}
		return exports
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
}

function isAppSpecifier(specifier: string): boolean {
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
		return new Set(Object.keys(parseJSONModule(source)))
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
