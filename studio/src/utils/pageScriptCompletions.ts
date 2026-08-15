import type { CompletionContext, CompletionResult } from "@codemirror/autocomplete"
import { isRef, unref } from "vue"
import useCodeStore from "@/stores/codeStore"
import type { CompletionSource } from "@/types"
import { getCompletions } from "./autocompletions"
import { vueImportCompletions } from "./vueApiCompletions"

// An ES module/standard app's page script's `setup(context)` param holds the page's runtime context. Treat that
// param as a single object whose members are the page's data sources, variables, route and router,
// then reuse the event-script completion engine — it reads nested objects straight off the live
// values, so `context.todos.data` completes the same way `todos.data` does in an event script.
// Anything that isn't a member access off the param falls back to Vue-API import completions.
export function pageScriptCompletions(context: CompletionContext): CompletionResult | null {
	return contextMemberCompletions(context) ?? vueImportCompletions(context)
}

function contextMemberCompletions(context: CompletionContext): CompletionResult | null {
	const param = getSetupContextParam(context.state.doc.toString())
	if (!param || !isMemberAccessOf(context, param)) return null
	return getCompletions(context, [contextSource(param)])
}

function contextSource(param: string): CompletionSource {
	return {
		item: buildContextItem(),
		completion: { label: param, type: "variable", detail: "Page Context" },
	}
}

// The shape the setup param holds at runtime. Variables and page-script bindings reach the script
// as refs, so surface them as `{ value }` — completion then offers `.value` and that value's own
// members, exactly like event scripts do.
function buildContextItem(): Record<string, any> {
	const codeStore = useCodeStore()
	const item: Record<string, any> = {}
	for (const [name, value] of Object.entries(codeStore.variables || {})) {
		item[name] = { value }
	}
	for (const [name, value] of Object.entries(codeStore.resources || {})) {
		item[name] = value
	}
	for (const [name, binding] of Object.entries(codeStore.pageScriptBindings || {})) {
		item[name] = isRef(binding) ? { value: unref(binding) } : binding
	}
	item.route = codeStore.routeObject?.value
	item.router = codeStore.routerObject
	return item
}

function isMemberAccessOf(context: CompletionContext, param: string): boolean {
	const line = context.state.doc.lineAt(context.pos)
	const before = line.text.slice(0, context.pos - line.from)
	const match = before.match(/([A-Za-z_$][\w$]*)(?:\.\w*)+$/)
	return Boolean(match && match[1] === param)
}

// Name of the setup context param, e.g. `context` in `export default function setup(context)`
// (or an arrow `export default (context) => …`). Returns null for destructured/missing params.
function getSetupContextParam(code: string): string | null {
	const named = code.match(/export\s+default\s+(?:async\s+)?function\s+setup\s*\(\s*([A-Za-z_$][\w$]*)/)
	if (named) return named[1]
	const arrow = code.match(/export\s+default\s+(?:async\s+)?\(?\s*([A-Za-z_$][\w$]*)\s*\)?\s*=>/)
	return arrow ? arrow[1] : null
}
