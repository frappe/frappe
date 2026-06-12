import { parse, parseExpressionAt } from "acorn"
import type { Node } from "acorn"
import { LRUCache } from "@/utils/cache"
import { isRef, unref } from "vue"

const fnCache = new LRUCache<boolean>(20)
export function isFunctionExpression(code: string): boolean {
	const trimmed = code.trimStart()
	if (
		!trimmed.startsWith("(") &&
		!trimmed.startsWith("function") &&
		!trimmed.startsWith("async") &&
		!code.includes("=>")
	) {
		return false
	}

	const cached = fnCache.get(code)
	if (cached !== undefined) return cached

	try {
		const ast = parse(code, { ecmaVersion: "latest", sourceType: "module" })
		if (ast.body.length === 1) {
			const node = ast.body[0]
			if (node.type === "ExpressionStatement") {
				const result =
					node.expression.type === "ArrowFunctionExpression" ||
					node.expression.type === "FunctionExpression"
				fnCache.set(code, result)
				return result
			}
		}
		fnCache.set(code, false)
		return false
	} catch {
		// anonymous `function(x) {}` doesn't parse as a program statement,
		// try parsing as an expression
		try {
			const expr = parseExpressionAt(code, 0, { ecmaVersion: "latest" })
			const result =
				expr.type === "ArrowFunctionExpression" ||
				expr.type === "FunctionExpression"
			fnCache.set(code, result)
			return result
		} catch {
			fnCache.set(code, false)
			return false
		}
	}
}

interface MemberExpressionNode extends Node {
	type: "MemberExpression"
	object: Node
	property: Node
	computed: boolean
	optional: boolean
}

const optionalChainingCache = new LRUCache<string>(20)
export function toOptionalChaining(expression: string): string {
	if (!expression.includes(".")) return expression

	const cached = optionalChainingCache.get(expression)
	if (cached !== undefined) return cached

	try {
		const ast = parse(expression, { ecmaVersion: "latest", sourceType: "module" })
		// Collect all dot positions that need to become ?.
		const dotPositions: number[] = []
		walkAST(ast, (node: Node) => {
			if (
				node.type === "MemberExpression" &&
				!(node as MemberExpressionNode).computed &&
				!(node as MemberExpressionNode).optional
			) {
				const memberNode = node as MemberExpressionNode
				// The dot is between object.end and property.start
				const dotIndex = expression.indexOf(".", memberNode.object.end!)
				if (dotIndex !== -1 && dotIndex < memberNode.property.start!) {
					dotPositions.push(dotIndex)
				}
			}
		})

		// Sort positions in reverse order to avoid index shifting during replacement
		dotPositions.sort((a, b) => b - a)

		let result = expression
		for (const pos of dotPositions) {
			result = result.slice(0, pos) + "?." + result.slice(pos + 1)
		}
		optionalChainingCache.set(expression, result)
		return result
	} catch {
		return expression
	}
}

// Collect every binding name a declaration pattern introduces, including
// destructuring (object/array/rest/default patterns).
function collectPatternNames(pattern: any, names: string[]) {
	if (!pattern) return
	switch (pattern.type) {
		case "Identifier":
			names.push(pattern.name)
			break
		case "ObjectPattern":
			for (const property of pattern.properties) {
				if (property.type === "RestElement") {
					collectPatternNames(property.argument, names)
				} else {
					collectPatternNames(property.value, names)
				}
			}
			break
		case "ArrayPattern":
			for (const element of pattern.elements) {
				// holes (e.g. `[, b]`) are null
				collectPatternNames(element, names)
			}
			break
		case "RestElement":
			collectPatternNames(pattern.argument, names)
			break
		case "AssignmentPattern":
			collectPatternNames(pattern.left, names)
			break
	}
}

const bindingNamesCache = new LRUCache<string[]>(20)
// All top-level bindings a script introduces: functions, classes, and variables
// (incl. destructured ones). Used to expose a client script's state like a <script setup>.
export function getTopLevelBindings(code: string): string[] {
	if (!code?.trim()) return []

	const cached = bindingNamesCache.get(code)
	if (cached !== undefined) return cached

	try {
		const ast = parse(code, { ecmaVersion: "latest", sourceType: "module" })
		const names: string[] = []
		for (const node of ast.body) {
			if (node.type === "FunctionDeclaration" || node.type === "ClassDeclaration") {
				if ((node as any).id) names.push((node as any).id.name)
			} else if (node.type === "VariableDeclaration") {
				for (const declaration of (node as any).declarations) {
					collectPatternNames(declaration.id, names)
				}
			}
		}
		bindingNamesCache.set(code, names)
		return names
	} catch {
		bindingNamesCache.set(code, [])
		return []
	}
}

// Describe a reactive binding's kind for display ("function" | "computed" | "ref" | typeof).
// A computed is a ref too, so isRef alone can't tell them apart; its internal `.effect` does.
export function getBindingType(binding: unknown): string {
	const unwrapped = unref(binding)
	if (typeof unwrapped === "function") return "function"
	if (isRef(binding)) return (binding as { effect?: unknown }).effect ? "computed" : "ref"
	return typeof unwrapped
}

export interface ScriptSyntaxError {
	message: string
	line: number
	column: number
}

// Validate a client script as a module and return the first syntax error (with position),
// or null if it parses. Used to block saving a broken script before it nukes the page.
export function getScriptError(code: string): ScriptSyntaxError | null {
	if (!code?.trim()) return null

	try {
		parse(code, { ecmaVersion: "latest", sourceType: "module" })
		return null
	} catch (error: any) {
		return {
			message: error.message,
			line: error.loc?.line ?? 0,
			column: error.loc?.column ?? 0,
		}
	}
}

function walkAST(node: any, callback: (node: Node) => void) {
	if (!node || typeof node !== "object") return

	callback(node)

	for (const key of Object.keys(node)) {
		const child = node[key]
		if (Array.isArray(child)) {
			for (const item of child) {
				if (item && typeof item === "object" && item.type) {
					walkAST(item, callback)
				}
			}
		} else if (child && typeof child === "object" && child.type) {
			walkAST(child, callback)
		}
	}
}
