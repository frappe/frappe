import { parse, parseExpressionAt } from "acorn"
import type { Node } from "acorn"
import { LRUCache } from "@/utils/cache"

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

const fnNamesCache = new LRUCache<string[]>(20)
export function getFunctionDeclarationNames(code: string): string[] {
	if (!code?.trim()) return []

	const cached = fnNamesCache.get(code)
	if (cached !== undefined) return cached

	try {
		const ast = parse(code, { ecmaVersion: "latest", sourceType: "module" })
		const names = ast.body
			.filter((node) => node.type === "FunctionDeclaration" && (node as any).id)
			.map((node) => (node as any).id.name as string)
		fnNamesCache.set(code, names)
		return names
	} catch {
		fnNamesCache.set(code, [])
		return []
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
