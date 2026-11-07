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

// Registry rebuilds can reuse compilation results when the source has not changed.
const cache = new Map<string, Promise<CompiledFile>>()

/** Convert ESM to CommonJS for the registry. The caller compiles each module once. */
export function compileFile(filename: string, source: string): Promise<CompiledFile> {
	const key = `${filename}\0${source.length}\0${djb2(source)}`
	let compiled = cache.get(key)
	if (!compiled) {
		compiled = toCommonJS(filename, source)
		cache.set(key, compiled)
	}
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
 * Read a module's dependencies and the names it exports, in one parse.
 *
 * Library modules load asynchronously, so the caller preloads them before synchronous require()
 * calls. Database apps require literal import() paths so both loaders can discover dependencies,
 * and their source must also satisfy moduleContract.ts.
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
		return {
			imports: [...staticImports(program), ...dynamicImports(program)],
			exports: exportedNames(program),
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

/** Find literal import() calls, including those nested inside expressions. */
function* dynamicImports(node: unknown): Generator<ModuleImport> {
	if (!node || typeof node !== "object") return
	if (Array.isArray(node)) {
		for (const item of node) yield* dynamicImports(item)
		return
	}
	const fields = node as Record<string, any>
	if (fields.type === "CallExpression" && fields.callee?.type === "Import") {
		const [argument] = fields.arguments
		if (argument?.type === "StringLiteral") yield { specifier: argument.value, names: [] }
	}
	for (const key in fields) {
		if (key !== "loc" && key !== "leadingComments" && key !== "trailingComments") {
			yield* dynamicImports(fields[key])
		}
	}
}

function exportedNames(program: BabelProgram): ModuleExports {
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
				const names: string[] = []
				declaredNames(node.declaration, names)
				for (const name of names) bindings[name] = { name }
			}
		}
	}
	return { bindings, starFrom }
}

function exportName(node: { type: string; name?: string; value?: string }): string {
	return node.type === "Identifier" ? node.name! : node.value!
}

/** Collect the names a declaration binds, including destructured ones. */
function declaredNames(node: any, names: string[]): void {
	if (!node || typeof node !== "object") return
	switch (node.type) {
		case "VariableDeclaration":
			for (const declarator of node.declarations) declaredNames(declarator.id, names)
			return
		case "Identifier":
			names.push(node.name)
			return
		case "ObjectPattern":
			for (const property of node.properties) {
				declaredNames(property.type === "RestElement" ? property.argument : property.value, names)
			}
			return
		case "ArrayPattern":
			for (const element of node.elements) declaredNames(element, names)
			return
		case "AssignmentPattern":
			declaredNames(node.left, names)
			return
		case "RestElement":
			declaredNames(node.argument, names)
			return
		default:
			if (node.id) declaredNames(node.id, names)
	}
}

function djb2(text: string): number {
	let hash = 5381
	for (let index = 0; index < text.length; index++) {
		hash = ((hash << 5) + hash + text.charCodeAt(index)) | 0
	}
	return hash
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
