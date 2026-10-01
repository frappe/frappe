import type { CompletionContext, CompletionResult } from "@codemirror/autocomplete"

// `route.name === "…"`, `name !== "…"`, `{ name: "…" }`: where router code names a page
const NAME_STRING = String.raw`\bname\s*(?:===?|!==?|:)\s*(["'])`
const OPEN_NAME_STRING = new RegExp(`${NAME_STRING}([^"']*)$`)
const NAME_STRINGS = new RegExp(`${NAME_STRING}(.*?)\\1`, "g")

// Studio's own record, see addNotFoundRouteFallback
const STUDIO_ROUTE_NAMES = ["Not Found"]

export function getPageNameCompletions(context: CompletionContext, pageTitles: string[]): CompletionResult | null {
	const line = context.state.doc.lineAt(context.pos)
	const match = OPEN_NAME_STRING.exec(line.text.slice(0, context.pos - line.from))
	if (!match) return null
	return {
		from: context.pos - match[2].length,
		options: pageTitles.map((title) => ({ label: title, type: "constant", detail: "page" })),
		validFor: /^[^"']*$/,
	}
}

export function findUnknownPageNames(source: string, pageTitles: string[]): string[] {
	const known = new Set([...pageTitles, ...STUDIO_ROUTE_NAMES])
	const names = [...source.matchAll(NAME_STRINGS)].map((match) => match[2])
	return [...new Set(names.filter((name) => !known.has(name)))]
}
