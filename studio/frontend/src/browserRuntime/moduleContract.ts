import { extractIdentifiers, walk, walkIdentifiers } from "vue/compiler-sfc"
import type { BabelProgram } from "@/browserRuntime/compiler"
import type { CompileError } from "@/browserRuntime/compiler"

const COMMONJS_NAMES = ["require", "module", "exports"]

/**
 * Report source the browser's CommonJS loader runs differently from a published bundle.
 *
 * Only divergences the loader cannot report itself belong here. Sucrase injects `require`,
 * `module` and `exports`, so source using those names works in the preview and breaks once the
 * app is built. A computed `import()` resolves against the page in the preview and against the
 * module in a build. Sucrase cannot parse a string-named import or export at all, and reports only
 * "Unexpected string".
 */
export function moduleSyntaxErrors(program: BabelProgram, filename: string): CompileError[] {
	const errors: CompileError[] = []
	const known: Record<string, number> = Object.create(null)
	const record = (node: any, message: string) =>
		errors.push({
			file: filename,
			line: node.loc?.start.line ?? null,
			column: node.loc?.start.column ?? null,
			message,
		})
	const bind = (id: any) => {
		if (known[id.name]) return
		known[id.name] = 1
		if (COMMONJS_NAMES.includes(id.name))
			record(id, `Top-level binding "${id.name}" is reserved in database apps.`)
	}
	for (const statement of program.body) {
		const node: any = (statement as any).declaration || statement
		if (node.type === "VariableDeclaration") {
			for (const declaration of node.declarations) {
				for (const id of extractIdentifiers(declaration.id)) bind(id)
			}
		} else if (node.id) bind(node.id)
		if (node.type === "ImportDeclaration") {
			for (const specifier of node.specifiers) bind(specifier.local)
		}
	}

	let functionDepth = 0
	walk(program, {
		enter(node: any) {
			if (isFunction(node)) functionDepth++
			// `var` hoists to the module, so a nested one still binds a top-level name.
			if (node.type === "VariableDeclaration" && node.kind === "var" && !functionDepth) {
				for (const declaration of node.declarations) {
					for (const id of extractIdentifiers(declaration.id)) bind(id)
				}
			}
			if (
				(node.type === "ImportSpecifier" && node.imported.type === "StringLiteral") ||
				(node.type === "ExportSpecifier" &&
					(node.local.type === "StringLiteral" || node.exported.type === "StringLiteral"))
			) {
				record(
					node,
					"String-named imports and exports are not supported in database apps. Use identifier names instead.",
				)
			}
			if (
				node.type === "CallExpression" &&
				node.callee.type === "Import" &&
				node.arguments[0]?.type !== "StringLiteral"
			) {
				record(node, "Dynamic imports in database apps must use a literal module path.")
			}
		},
		leave(node: any) {
			if (isFunction(node)) functionDepth--
		},
	})

	if (program.body.length) {
		walkIdentifiers(
			program as any,
			(id, _parent, _stack, isReference, isLocal) => {
				if (isReference && !isLocal && COMMONJS_NAMES.includes(id.name)) {
					record(id, `${id.name} is not available in database app source. Use import and export instead.`)
				}
			},
			false,
			[],
			known,
		)
	}
	return errors
}

function isFunction(node: { type: string }): boolean {
	return node.type.includes("Function") || node.type.endsWith("Method")
}
