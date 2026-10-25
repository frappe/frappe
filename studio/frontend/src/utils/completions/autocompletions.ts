import type { Completion, CompletionContext } from "@codemirror/autocomplete"
import type { CompletionSource } from "@/types"

export const getCompletions = (context: CompletionContext, sources?: CompletionSource[]) => {
	const line = context.state.doc.lineAt(context.pos)
	const lineText = line.text
	const cursorPos = context.pos - line.from
	const textBeforeCursor = lineText.slice(0, cursorPos)

	// Check if we're completing after a dot - property access for an object / object inside an array
	// items. OR items.data[0].
	const propertyAccessMatch = textBeforeCursor.match(/([\w.]+(?:\[\d+\])*(?:\.[\w]*)*)\.$/)
	let completionObject

	if (propertyAccessMatch) {
		const chain = parseObjectChain(textBeforeCursor)
		const completions: Completion[] = []
		addNestedCompletions(completions, chain, sources)

		completionObject = {
			from: context.pos,
			options: completions,
			validFor: /^\w*$/,
		}
	} else {
		let word = context.matchBefore(/\w*/)
		if (!word || (word.from === word.to && !context.explicit)) return null

		const completions: Completion[] = []
		addRootCompletions(completions, sources)

		completionObject = {
			from: word.from, // Start of the word for replacement
			options: completions,
			validFor: /^\w*$/,
		}
	}

	if (context.explicit) {
		// boost score for custom completions over language completions when explicitly requested
		return {
			...completionObject,
			options: completionObject.options.map((option) => ({
				...option,
				boost: 10
			}))
		}
	}
	return completionObject
}

function addRootCompletions(completions: Completion[], sources?: CompletionSource[]) {
	sources?.forEach(source => {
		completions.push({
			...source.completion
		})
	})
}

function parseObjectChain(text: string) {
	// Match patterns like word. or word[index].
	const matches = text.match(/([\w]+(?:\.[\w]+|\[\d+\])*(?:\.[\w]*)*)\.$/)
	if (!matches) return []

	const chain = matches[1]
	const parts = []
	let current = ""
	let inBrackets = false

	for (let i = 0; i < chain.length; i++) {
		const char = chain[i]

		if (char === "[") {
			if (current) {
				parts.push(current)
				current = ""
			}
			inBrackets = true
		} else if (char === "]") {
			if (current) {
				parts.push(current)
				current = ""
			}
			inBrackets = false
		} else if (char === "." && !inBrackets) {
			if (current) {
				parts.push(current)
				current = ""
			}
		} else {
			current += char
		}
	}

	if (current) {
		parts.push(current)
	}

	return parts.filter(part => part !== "")
}

function getNestedValue(obj: Record<string, any>, chain: string[]) {
	let current = obj
	for (const key of chain) {
		if (current === null || current === undefined) return null

		if (Array.isArray(current) && !isNaN(parseInt(key))) {
			current = current[parseInt(key)]
		} else if (typeof current === "object" && !Array.isArray(current)) {
			current = current[key]
		} else {
			return null
		}
	}
	return current
}

function addNestedCompletions(completions: Completion[], chain: string[], sources?: CompletionSource[]) {
	const rootKey = chain[0]
	const remainingChain = chain.slice(1)

	let targetObject = null
	const source = sources?.find(c => c.completion.label === rootKey)
	if (source && typeof source.item === "object") {
		targetObject = source.item
	}

	if (!targetObject) return

	const nestedObject = getNestedValue(targetObject, remainingChain)
	if (!nestedObject) return

	if (Array.isArray(nestedObject)) {
		addArrayCompletions(completions, nestedObject)
	} else if (typeof nestedObject === "object" && nestedObject !== null) {
		addObjectCompletions(completions, nestedObject)
	}
}

function addArrayCompletions(completions: Completion[], array: any[]) {
	if (array.length === 0) return
	for (let i = 0; i < Math.min(array.length, 5); i++) {
		completions.push({
			label: `[${i}]`,
			type: "property",
			detail: `Array index ${i}`,
		})
	}

	if (typeof array[0] === "object") {
		Object.keys(array[0]).forEach((key) => {
			completions.push({
				label: `[0].${key}`,
				type: "property",
				detail: `Property of first item: ${key}`,
			})
		})
	}
}

function addObjectCompletions(completions: Completion[], obj: Record<string, any>) {
	Object.keys(obj).forEach((key) => {
		const value = obj[key]
		let type = "property"
		let detail = `Property: ${key}`

		if (Array.isArray(value)) {
			type = "array"
			detail = `Array property (${value.length} items)`
		} else if (typeof value === "function") {
			type = "method"
			detail = "Method"
		} else if (typeof value === "object" && value !== null) {
			type = "object"
			detail = "Object property"
		} else {
			detail = `${typeof value} property`
		}

		completions.push({
			label: key,
			type: type,
			detail: detail,
		})
	})
}
