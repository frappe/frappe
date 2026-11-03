/**
 * Compiles a Studio app's source files in the browser: Vue SFCs through vue/compiler-sfc,
 * TypeScript stripped (never type-checked) with sucrase. This is what a database app has
 * instead of Vite — a repository app's files are built ahead of time and never come through here.
 *
 * The compilers load lazily, so an app that ships a build never downloads them.
 */

export interface CompileError {
	file: string
	line: number | null
	column: number | null
	message: string
}

export interface CompiledFile {
	code: string
	css: string
	errors: CompileError[]
}

export interface ModuleImport {
	specifier: string
	/** The names a static import takes, for the export check; empty for a re-export or `import()`. */
	names: string[]
}

export function describeError(error: CompileError): string {
	const place = error.file ? `${error.file}${error.line ? `:${error.line}` : ""}: ` : ""
	return `${place}${error.message}`
}

const TS_OPTIONS: SucraseOptions = { transforms: ["typescript"], disableESTransforms: true }
// Modules execute as CommonJS in the registry (see moduleRegistry.ts), so an import cycle
// resolves the way it does in Node and in a bundler: the partly filled exports object.
const CJS_OPTIONS: SucraseOptions = { transforms: ["imports"], disableESTransforms: true }

type SucraseOptions = import("sucrase").Options
type BabelProgram = ReturnType<typeof import("vue/compiler-sfc").babelParse>["program"]
type ImportDeclaration = Extract<BabelProgram["body"][number], { type: "ImportDeclaration" }>

let compilerModules: Promise<[typeof import("vue/compiler-sfc"), typeof import("sucrase")]> | null = null

function loadCompilers() {
	compilerModules ??= Promise.all([import("vue/compiler-sfc"), import("sucrase")])
	return compilerModules
}

// Compiles are cheap (a few ms per file) but run on every runtime rebuild, so memoize by content.
const cache = new Map<string, Promise<CompiledFile>>()

export function compileFile(filename: string, source: string): Promise<CompiledFile> {
	const key = `${filename}\0${source.length}\0${djb2(source)}`
	let compiled = cache.get(key)
	if (!compiled) {
		compiled = filename.endsWith(".vue") ? compileSFC(filename, source) : compileTS(filename, source)
		cache.set(key, compiled)
	}
	return compiled
}

async function compileTS(filename: string, source: string): Promise<CompiledFile> {
	const [, sucrase] = await loadCompilers()
	try {
		const code = sucrase.transform(source, { ...TS_OPTIONS, filePath: filename }).code
		return { code, css: "", errors: [] }
	} catch (error) {
		return { code: "", css: "", errors: [formatError(filename, error)] }
	}
}

/** ESM to CommonJS, for the module registry. Not cached: callers transform compiled output once. */
export async function toCommonJS(filename: string, source: string): Promise<CompiledFile> {
	const [, sucrase] = await loadCompilers()
	try {
		const code = sucrase.transform(source, { ...CJS_OPTIONS, filePath: filename }).code
		return { code, css: "", errors: [] }
	} catch (error) {
		return { code: "", css: "", errors: [formatError(filename, error)] }
	}
}

/**
 * Every import in compiled module code, with the names each one takes. The registry needs these
 * before any module body runs, because its require is synchronous while loading a bare module is
 * not. A computed `import()` carries no specifier to read, so it falls through to that require.
 */
export async function parseImports(
	filename: string,
	code: string,
): Promise<{ imports: ModuleImport[]; errors: CompileError[] }> {
	const [sfc] = await loadCompilers()
	try {
		const { program } = sfc.babelParse(code, { sourceType: "module" })
		return { imports: [...staticImports(program), ...dynamicImports(program)], errors: [] }
	} catch (error) {
		return { imports: [], errors: [formatError(filename, error)] }
	}
}

function* staticImports(program: BabelProgram): Generator<ModuleImport> {
	for (const node of program.body) {
		if (node.type === "ImportDeclaration") {
			if (node.importKind === "type") continue
			yield { specifier: node.source.value, names: importedNames(node) }
		} else if ("source" in node && node.source) {
			// `export … from "…"` pulls the module in without naming what it takes
			yield { specifier: node.source.value, names: [] }
		}
	}
}

function importedNames(node: ImportDeclaration): string[] {
	const names: string[] = []
	for (const specifier of node.specifiers) {
		if (specifier.type !== "ImportSpecifier" || specifier.importKind === "type") continue
		const { imported } = specifier
		names.push(imported.type === "Identifier" ? imported.name : imported.value)
	}
	return names
}

/** `import("…")` sits in an expression, so it takes a walk to find. */
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

async function compileSFC(filename: string, source: string): Promise<CompiledFile> {
	const [sfc] = await loadCompilers()
	const id = scopeId(filename)
	const { descriptor, errors: parseErrors } = sfc.parse(source, { filename })
	// stop on parse errors before compileScript: with inlineTemplate a broken template compiles
	// into a component that renders wrong instead of failing
	if (parseErrors.length) {
		return { code: "", css: "", errors: parseErrors.map((error) => formatError(filename, error)) }
	}

	const unsupported = findUnsupportedLang(descriptor)
	if (unsupported) {
		return { code: "", css: "", errors: [{ file: filename, line: null, column: null, message: unsupported }] }
	}

	const hasTS = descriptor.script?.lang === "ts" || descriptor.scriptSetup?.lang === "ts"
	const hasScopedStyle = descriptor.styles.some((style) => style.scoped)

	// compileScript inlines the template only for <script setup>, and throws on an SFC with no
	// script at all, so every other shape compiles its template separately
	const inlineTemplate = Boolean(descriptor.scriptSetup)

	let code: string
	if (descriptor.script || descriptor.scriptSetup) {
		try {
			code = sfc.compileScript(descriptor, { id, inlineTemplate, genDefaultAs: "__sfc__" }).content
		} catch (error) {
			return { code: "", css: "", errors: [formatError(filename, error)] }
		}
	} else {
		code = "const __sfc__ = {}\n"
	}

	// no <template> means the script is the whole component: it may carry its own render option
	if (!inlineTemplate && descriptor.template) {
		const template = sfc.compileTemplate({
			source: descriptor.template.content,
			filename,
			id,
			scoped: hasScopedStyle,
		})
		if (template.errors.length) {
			return { code: "", css: "", errors: template.errors.map((error) => formatError(filename, error)) }
		}
		code += `\n${template.code}\n__sfc__.render = render\n`
	}
	if (hasTS) {
		// one pass over the whole output also strips the TS casts inline templates leave in render code
		const stripped = await compileTS(filename, code)
		if (stripped.errors.length) return stripped
		code = stripped.code
	}

	let css = ""
	const cssErrors: CompileError[] = []
	for (const style of descriptor.styles) {
		const result = await sfc.compileStyleAsync({
			source: style.content,
			filename,
			id: `data-v-${id}`,
			scoped: style.scoped,
		})
		cssErrors.push(...result.errors.map((error) => formatError(filename, error)))
		css += result.code
	}
	if (cssErrors.length) return { code: "", css: "", errors: cssErrors }

	code += `\n__sfc__.__file = ${JSON.stringify(filename)}\n`
	if (hasScopedStyle) code += `__sfc__.__scopeId = ${JSON.stringify(`data-v-${id}`)}\n`
	code += "export default __sfc__\n"
	return { code, css, errors: [] }
}

/**
 * There are no preprocessors in the browser. A block Vite would hand to sass or esbuild-jsx
 * reaches the plain compiler here, which accepts it and emits wrong output instead of failing,
 * so reject the language before anything compiles.
 */
function findUnsupportedLang(descriptor: import("vue/compiler-sfc").SFCDescriptor): string | null {
	for (const block of [descriptor.script, descriptor.scriptSetup]) {
		if (block?.lang && block.lang !== "ts" && block.lang !== "js") {
			return unsupportedMessage("script", block.lang, "TypeScript or JavaScript")
		}
	}
	if (descriptor.template?.lang && descriptor.template.lang !== "html") {
		return unsupportedMessage("template", descriptor.template.lang, "plain HTML")
	}
	for (const style of descriptor.styles) {
		if (style.lang && style.lang !== "css") {
			return unsupportedMessage("style", style.lang, "plain CSS")
		}
	}
	return null
}

function unsupportedMessage(block: string, lang: string, instead: string): string {
	return (
		`<${block} lang="${lang}"> is not supported in a database app: the browser has no ` +
		`${lang} compiler. Use ${instead}, or export the app to a repository to build it with Vite.`
	)
}

/** Stable short id per filename, used as the scoped-style hash so scoped CSS survives edits. */
function scopeId(filename: string): string {
	return (djb2(filename) >>> 0).toString(16).padStart(8, "0")
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
