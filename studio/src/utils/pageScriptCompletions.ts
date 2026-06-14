import type { Completion, CompletionContext, CompletionResult } from "@codemirror/autocomplete"
import useCodeStore from "@/stores/codeStore"
import { vueImportCompletions } from "./vueApiCompletions"

// A code-mode page script's `setup(context)` param holds the page's runtime context — its data
// sources, variables, route and router. Complete those as members of that param; anything else
// falls back to the Vue-API import completions.
export function pageScriptCompletions(context: CompletionContext): CompletionResult | null {
	return contextMemberCompletions(context) ?? vueImportCompletions(context)
}

function contextMemberCompletions(context: CompletionContext): CompletionResult | null {
	const before = context.matchBefore(/\w+\.\w*/)
	if (!before) return null
	const [identifier] = before.text.split(".")
	if (identifier !== getSetupContextParam(context.state.doc.toString())) return null
	return {
		from: before.from + identifier.length + 1, // right after the dot
		options: studioContextOptions(),
		validFor: /^\w*$/,
	}
}

function studioContextOptions(): Completion[] {
	const codeStore = useCodeStore()
	const options: Completion[] = []
	for (const name of Object.keys(codeStore.resources || {})) {
		options.push({ label: name, type: "data", detail: "Data Source" })
	}
	for (const name of Object.keys(codeStore.variables || {})) {
		options.push({ label: name, type: "variable", detail: "Variable" })
	}
	options.push(
		{ label: "route", type: "variable", detail: "Vue Router Route" },
		{ label: "router", type: "variable", detail: "Vue Router" },
	)
	return options
}

// Name of the setup context param, e.g. `context` in `export default function setup(context)`
// (or an arrow `export default (context) => …`). Returns null for destructured/missing params.
function getSetupContextParam(code: string): string | null {
	const named = code.match(/export\s+default\s+(?:async\s+)?function\s+setup\s*\(\s*([A-Za-z_$][\w$]*)/)
	if (named) return named[1]
	const arrow = code.match(/export\s+default\s+(?:async\s+)?\(?\s*([A-Za-z_$][\w$]*)\s*\)?\s*=>/)
	return arrow ? arrow[1] : null
}
