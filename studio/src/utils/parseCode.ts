import { parse, parseExpressionAt } from "acorn"
import type { Node } from "acorn"

/**
 * Detect if a string is a function expression (arrow function, function expression, etc.)
 * Uses AST parsing instead of regex for reliability with edge cases like:
 * - destructured params: ({a, b}) => {}
 * - default values: (a = 1) => {}
 * - async functions: async function(e) {}
 * - named function expressions: function handler(e) {}
 */
export function isFunctionExpression(code: string): boolean {
	// Try parsing as a full program first
	try {
		const ast = parse(code, { ecmaVersion: "latest", sourceType: "module" })
		if (ast.body.length === 1) {
			const node = ast.body[0]
			if (node.type === "ExpressionStatement") {
				return (
					node.expression.type === "ArrowFunctionExpression" ||
					node.expression.type === "FunctionExpression"
				)
			}
		}
		return false
	} catch {
		// bare `function(x) {}` doesn't parse as a program statement,
		// try parsing as an expression
		try {
			const expr = parseExpressionAt(code, 0, { ecmaVersion: "latest" })
			return (
				expr.type === "ArrowFunctionExpression" ||
				expr.type === "FunctionExpression"
			)
		} catch {
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

/**
 * Convert member expressions (a.b.c) to optional chaining (a?.b?.c)
 * via AST walking. Only targets non-computed, non-optional MemberExpression nodes.
 *
 * Unlike the regex approach, this correctly handles:
 * - Method calls: items.filter(i => i.active) — chains are handled, arrow is untouched
 * - Computed access: obj[key].name — skips the computed [key] part
 * - String literals — untouched
 * - Ternaries — each branch handled independently
 */
export function toOptionalChaining(expression: string): string {
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

		if (dotPositions.length === 0) return expression

		// Sort positions in reverse order to avoid index shifting during replacement
		dotPositions.sort((a, b) => b - a)

		let result = expression
		for (const pos of dotPositions) {
			result = result.slice(0, pos) + "?." + result.slice(pos + 1)
		}
		return result
	} catch {
		// If parsing fails, return expression as-is
		return expression
	}
}

/**
 * Simple recursive AST walker
 */
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
