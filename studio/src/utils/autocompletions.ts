import useStudioStore from "@/stores/studioStore"
import type { Completion, CompletionContext } from "@codemirror/autocomplete"

const store = useStudioStore()

export const getCompletions = (context: CompletionContext) => {
	const line = context.state.doc.lineAt(context.pos)
	const lineText = line.text
	const cursorPos = context.pos - line.from
	const textBeforeCursor = lineText.slice(0, cursorPos)

	// Check if we're completing after a dot (property access)
	const propertyAccessMatch = textBeforeCursor.match(/([\w.]+)\.(\w*)$/)

	if (propertyAccessMatch) {
		const chain = parseObjectChain(textBeforeCursor)
		const completions: Completion[] = []
		addNestedCompletions(completions, chain)

		return {
			from: context.pos,
			options: completions,
			validFor: /^\w*$/,
		}
	} else {
		let word = context.matchBefore(/\w*/)
		if (!word || (word.from === word.to && !context.explicit)) return null

		const completions: Completion[] = []
		addRootCompletions(completions)

		return {
			from: word.from, // Start of the word for replacement
			options: completions,
			validFor: /^\w*$/,
		}
	}
}

function addRootCompletions(completions: Completion[]) {
	Object.keys(store.variables || {}).forEach((variable) => {
		completions.push({
			label: variable,
			type: "variable",
			detail: "Variable",
		})
	})

	Object.keys(store.resources || {}).forEach((resource) => {
		completions.push({
			label: resource,
			type: "data",
			detail: "Data Source",
		})
	})
}

function parseObjectChain(text: string) {
	// Match patterns like: word.word[index].word
	const matches = text.match(/([\w]+(?:\.[\w]+|\[\d+\])*)\.$/)
	if (!matches) return []

	const chain = matches[1]
	// Split by dots and handle array indices
	return chain.split(/[.\[\]]/).filter((part) => part !== "")
}

function getNestedValue(obj, chain) {
	let current = obj
	for (const key of chain) {
		if (current === null || current === undefined) return null

		if (Array.isArray(current) && !isNaN(key)) {
			current = current[parseInt(key)]
		} else if (typeof current === "object") {
			current = current[key]
		} else {
			return null
		}
	}
	return current
}

function addNestedCompletions(completions: Completion[], chain) {
	const rootKey = chain[0]
	const remainingChain = chain.slice(1)

	let targetObject = null

	if (store.variables && store.variables[rootKey]) {
		targetObject = store.variables[rootKey]
	} else if (store.resources && store.resources[rootKey]) {
		targetObject = store.resources[rootKey]
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

function addArrayCompletions(completions: Completion[], array) {
	for (let i = 0; i < Math.min(array.length, 5); i++) {
		completions.push({
			label: `[${i}]`,
			type: "property",
			detail: `Array index ${i}`,
		})
	}

	if (array.length > 0 && typeof array[0] === "object") {
		Object.keys(array[0]).forEach((key) => {
			completions.push({
				label: `[0].${key}`,
				type: "property",
				detail: `Property of first item: ${key}`,
			})
		})
	}
}

function addObjectCompletions(completions: Completion[], obj) {
	Object.keys(obj).forEach((key) => {
		const value = obj[key]
		let type = "property"
		let detail = `Property: ${key}`

		if (Array.isArray(value)) {
			type = "array"
			detail = `Array property (${value.length} items)`
		} else if (typeof value === "function") {
			type = "method"
			detail = `Method: ${key}()`
		} else if (typeof value === "object" && value !== null) {
			type = "object"
			detail = "Object property"
		} else {
			detail = `${typeof value}`
		}

		completions.push({
			label: key,
			type: type,
			detail: detail,
		})
	})
}
