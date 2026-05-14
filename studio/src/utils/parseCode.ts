import { parse, parseExpressionAt } from "acorn"
import type { Node } from "acorn"

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

export function toOptionalChaining(expression: string): string {
	if (!expression.includes(".")) return expression

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
