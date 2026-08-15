import type { Completion, CompletionContext, CompletionResult } from "@codemirror/autocomplete"
import type { EditorView } from "@codemirror/view"
import type { EditorState } from "@codemirror/state"
import { syntaxTree } from "@codemirror/language"
import type { CompletionSource } from "@/types"
import { vueReactivityApis } from "@/stores/codeStore"

// Single source of truth: the Vue APIs injected into interpreted scripts are also the ones we
// suggest (and auto-import) in code files.
const VUE_API_NAMES = Object.keys(vueReactivityApis)

// Interpreted page script: the APIs are injected into its scope, so completion just inserts a call.
export function vueApiSources(): CompletionSource[] {
	return VUE_API_NAMES.map((name) => ({
		item: undefined,
		completion: {
			label: name,
			type: "function",
			detail: "Vue API",
			apply: insertCall(name),
		},
	}))
}

// Code files (.ts/.js/.vue): insert the call and add `import { name } from "vue"` if it's missing.
export function vueImportCompletions(context: CompletionContext): CompletionResult | null {
	const word = context.matchBefore(/\w*/)
	if (!word || (word.from === word.to && !context.explicit)) return null
	return {
		from: word.from,
		options: VUE_API_NAMES.map(
			(name): Completion => ({
				label: name,
				type: "function",
				detail: "vue",
				apply: insertCallWithImport(name),
			}),
		),
		validFor: /^\w*$/,
	}
}

function insertCall(name: string) {
	return (view: EditorView, _completion: Completion, from: number, to: number) => {
		const insert = `${name}()`
		view.dispatch({
			changes: { from, to, insert },
			selection: { anchor: from + insert.length - 1 }, // cursor inside the parentheses
		})
	}
}

function insertCallWithImport(name: string) {
	return (view: EditorView, _completion: Completion, from: number, to: number) => {
		// Inside an `import { … }` the user is listing the name, not calling it: insert it bare and
		// don't add another import.
		if (isInsideImport(view.state, from)) {
			view.dispatch({ changes: { from, to, insert: name } })
			return
		}
		const insert = `${name}()`
		const importChange = vueImportChange(view, name)
		// the import is added above the cursor, so it shifts where the call lands
		const shift = importChange ? importChange.insert.length : 0
		view.dispatch({
			changes: importChange ? [importChange, { from, to, insert }] : { from, to, insert },
			selection: { anchor: from + shift + insert.length - 1 },
		})
	}
}

function isInsideImport(state: EditorState, pos: number): boolean {
	let node = syntaxTree(state).resolveInner(pos, -1)
	while (true) {
		if (node.name.includes("Import")) return true
		const parent = node.parent
		if (!parent) return false
		node = parent
	}
}

// The change that makes `name` importable from "vue": merge into an existing import, or add one.
function vueImportChange(view: EditorView, name: string): { from: number; insert: string } | null {
	const text = view.state.doc.toString()
	const match = /import\s*\{([^}]*)\}\s*from\s*['"]vue['"]/.exec(text)
	if (!match) {
		return { from: 0, insert: `import { ${name} } from "vue"\n` }
	}
	const imported = match[1]
		.split(",")
		.map((part) => part.trim())
		.filter(Boolean)
	if (imported.includes(name)) return null
	let pos = match.index + match[0].indexOf("{") + 1
	while (/\s/.test(text[pos] ?? "")) pos++
	return { from: pos, insert: `${name}, ` }
}
