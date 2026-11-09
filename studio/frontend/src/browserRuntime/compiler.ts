/**
 * Convert stored source to CommonJS in the browser with Sucrase, and read its imports and exports
 * with vue/compiler-sfc's Babel parser. This supports database apps without a server build and
 * syntax checking in the editor.
 *
 * A database app stores JavaScript, so nothing here compiles another language. TypeScript syntax
 * is a syntax error in a .js file, as it is anywhere else; only the editor's syntax check parses
 * it, for a repository app's .ts script.
 *
 * Load the compilers only when needed. Built apps exclude this module.
 */

export interface CompileError {
	file: string
	line: number | null
	column: number | null
	message: string
}

interface CompiledFile {
	code: string
	errors: CompileError[]
}

export interface ModuleImport {
	specifier: string
	/** Requested exports, including "default". Namespace and dynamic imports have no names. */
	names: string[]
}

export interface ModuleExports {
	/** `export { count as total } from "./state"` records total -> { name: "count", from: "./state" }.
	 * Local declarations omit `from`; the registry follows re-exports to their original binding. */
	bindings: Record<string, { name: string; from?: string }>
	/** Specifiers it re-exports every name from, whose names it also exports. */
	starFrom: string[]
}

export interface ParsedModule {
	imports: ModuleImport[]
	exports: ModuleExports
	errors: CompileError[]
}

export function describeError(error: CompileError): string {
	const place = error.file ? `${error.file}${error.line ? `:${error.line}` : ""}: ` : ""
	return `${place}${error.message}`
}

// The registry executes CommonJS modules. Cycles can read a module's exports before it finishes.
const CJS_OPTIONS: SucraseOptions = { transforms: ["imports"], disableESTransforms: true }

type SucraseOptions = import("sucrase").Options
export type BabelProgram = ReturnType<typeof import("vue/compiler-sfc").babelParse>["program"]
type ImportDeclaration = Extract<BabelProgram["body"][number], { type: "ImportDeclaration" }>

let compilerModules: Promise<[typeof import("vue/compiler-sfc"), typeof import("sucrase")]> | null = null

function loadCompilers() {
	compilerModules ??= Promise.all([import("vue/compiler-sfc"), import("sucrase")])
	return compilerModules
}

// Hold the latest compilation of each file, so a rebuild reuses the files that did not change.
// Keying by path replaces a superseded version instead of keeping it, and holds every file of an
// app however large it is.
const cache = new Map<string, { source: string; compiled: Promise<CompiledFile> }>()

/** Convert ESM to CommonJS for the registry. The caller compiles each module once. */
export function compileFile(filename: string, source: string): Promise<CompiledFile> {
	const cached = cache.get(filename)
	if (cached?.source === source) return cached.compiled
	const compiled = toCommonJS(filename, source)
	cache.set(filename, { source, compiled })
	return compiled
}

async function toCommonJS(filename: string, source: string): Promise<CompiledFile> {
	const [, sucrase] = await loadCompilers()
	try {
		const code = sucrase.transform(source, { ...CJS_OPTIONS, filePath: filename }).code
		return { code, errors: [] }
	} catch (error) {
		return { code: "", errors: [formatError(filename, error)] }
	}
}

/**
 * Read a module's dependencies and the names it exports.
 *
 * Library modules load asynchronously, so the caller preloads them before synchronous require()
 * calls. Database apps require literal import() paths so both loaders can discover dependencies,
 * and their source must also satisfy moduleContract.js.
 */
export async function parseModule(
	filename: string,
	code: string,
	databaseApp = false,
): Promise<ParsedModule> {
	const [sfc] = await loadCompilers()
	try {
		const { program } = sfc.babelParse(code, {
			sourceType: "module",
			plugins: filename.endsWith(".ts") ? ["typescript"] : [],
		})
		if (databaseApp) {
			const { moduleSyntaxErrors } = await import("@/browserRuntime/moduleContract")
			const errors = moduleSyntaxErrors(program, filename)
			if (errors.length) return { ...nothingParsed(), errors }
		}
		const imports = [...staticImports(program)]
		sfc.walk(program, {
			enter(node: any) {
				if (node.type === "CallExpression" && node.callee.type === "Import") {
					const [argument] = node.arguments
					if (argument?.type === "StringLiteral") imports.push({ specifier: argument.value, names: [] })
				}
			},
		})
		return {
			imports,
			exports: exportedNames(program, sfc.extractIdentifiers),
			errors: [],
		}
	} catch (error) {
		return { ...nothingParsed(), errors: [formatError(filename, error)] }
	}
}

function nothingParsed(): ParsedModule {
	return { imports: [], exports: { bindings: {}, starFrom: [] }, errors: [] }
}

function* staticImports(program: BabelProgram): Generator<ModuleImport> {
	for (const node of program.body) {
		if (node.type === "ImportDeclaration") {
			if (node.importKind === "type") continue
			yield { specifier: node.source.value, names: importedNames(node) }
		} else if (node.type === "ExportNamedDeclaration" && node.source && node.exportKind !== "type") {
			const names = node.specifiers.flatMap((specifier) => {
				if (specifier.type !== "ExportSpecifier" || specifier.exportKind === "type") return []
				return [exportName(specifier.local)]
			})
			yield { specifier: node.source.value, names }
		} else if (node.type === "ExportAllDeclaration") {
			yield { specifier: node.source.value, names: [] }
		}
	}
}

function importedNames(node: ImportDeclaration): string[] {
	const names: string[] = []
	for (const specifier of node.specifiers) {
		if (specifier.type === "ImportDefaultSpecifier") names.push("default")
		if (specifier.type !== "ImportSpecifier" || specifier.importKind === "type") continue
		const { imported } = specifier
		names.push(imported.type === "Identifier" ? imported.name : imported.value)
	}
	return names
}

function exportedNames(
	program: BabelProgram,
	extractIdentifiers: typeof import("vue/compiler-sfc").extractIdentifiers,
): ModuleExports {
	const bindings: ModuleExports["bindings"] = Object.create(null)
	const starFrom: string[] = []
	const imports: ModuleExports["bindings"] = Object.create(null)
	for (const node of program.body) {
		if (node.type !== "ImportDeclaration" || node.importKind === "type") continue
		for (const specifier of node.specifiers) {
			if (specifier.type === "ImportSpecifier" && specifier.importKind === "type") continue
			const name =
				specifier.type === "ImportSpecifier"
					? exportName(specifier.imported)
					: specifier.type === "ImportDefaultSpecifier"
						? "default"
						: "*"
			imports[specifier.local.name] = { name, from: node.source.value }
		}
	}
	for (const node of program.body) {
		if (node.type === "ExportDefaultDeclaration") {
			bindings.default = {
				name: "id" in node.declaration && node.declaration.id ? node.declaration.id.name : "*default*",
			}
		} else if (node.type === "ExportAllDeclaration") {
			starFrom.push(node.source.value)
		} else if (node.type === "ExportNamedDeclaration" && node.exportKind !== "type") {
			for (const specifier of node.specifiers) {
				if (specifier.type === "ExportSpecifier" && specifier.exportKind === "type") continue
				const local = specifier.type === "ExportSpecifier" ? exportName(specifier.local) : "*"
				bindings[exportName(specifier.exported)] = node.source
					? { name: local, from: node.source.value }
					: imports[local] || { name: local }
			}
			if (node.declaration) {
				const declaration = node.declaration
				const identifiers =
					declaration.type === "VariableDeclaration"
						? declaration.declarations.flatMap(({ id }) => extractIdentifiers(id))
						: "id" in declaration && declaration.id?.type === "Identifier"
							? [declaration.id]
							: []
				for (const { name } of identifiers) bindings[name] = { name }
			}
		}
	}
	return { bindings, starFrom }
}

function exportName(node: { type: string; name?: string; value?: string }): string {
	return node.type === "Identifier" ? node.name! : node.value!
}

function formatError(filename: string, error: any): CompileError {
	const location = error?.loc?.start || error?.loc || {}
	return {
		file: filename,
		line: location.line ?? null,
		column: location.column ?? null,
		message: error?.message || String(error),
	}
}
