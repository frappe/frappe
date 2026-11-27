/**
 * The rules for database app source.
 *
 * Reject code that the browser loader or the app build cannot run. The two call this function,
 * so preview and build fail on the same code.
 */

import { extractIdentifiers, walk, walkIdentifiers } from "vue/compiler-sfc"
import { IMPORTABLE_MODULES } from "./importableModuleNames.js"

const COMMONJS_NAMES = ["require", "module", "exports"]

/**
 * @param {import('./compiler').BabelProgram} program
 * @param {string} filename
 * @returns {import('./compiler').CompileError[]}
 */
export function moduleSyntaxErrors(program, filename) {
	const errors = []
	const known = Object.create(null)
	const record = (node, message) =>
		errors.push({
			file: filename,
			line: node.loc?.start.line ?? null,
			column: node.loc?.start.column ?? null,
			message,
		})
	const bind = (id) => {
		if (known[id.name]) return
		known[id.name] = 1
		if (COMMONJS_NAMES.includes(id.name))
			record(id, `Top-level binding "${id.name}" is reserved in database apps.`)
	}
	for (const statement of program.body) {
		const node = statement.declaration || statement
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
		enter(node) {
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
			if (node.type === "MetaProperty" && node.meta.name === "import") {
				record(node, "import.meta is not supported in database apps.")
			}
			const source =
				node.source || (node.type === "CallExpression" && node.callee.type === "Import" && node.arguments[0])
			if (source?.type === "StringLiteral") {
				const specifier = source.value
				if (specifier.includes("?") || specifier.includes("#")) {
					record(node, "Import queries and fragments are not supported in database apps.")
				} else if (
					!specifier.startsWith(".") &&
					!specifier.startsWith("@app/") &&
					!IMPORTABLE_MODULES.includes(specifier)
				) {
					record(node, `"${specifier}" is not importable in a database app.`)
				}
				if (node.attributes?.length || node.assertions?.length || node.arguments?.length > 1) {
					record(node, "Import attributes are not supported in database apps.")
				}
			}
		},
		leave(node) {
			if (isFunction(node)) functionDepth--
		},
	})

	if (program.body.length) {
		walkIdentifiers(
			program,
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

function isFunction(node) {
	return node.type.includes("Function") || node.type.endsWith("Method")
}
