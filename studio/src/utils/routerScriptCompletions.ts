import type { CompletionContext, CompletionResult } from "@codemirror/autocomplete"
import { createMemoryHistory, createRouter, type RouteRecordRaw } from "vue-router"
import type { CompletionSource } from "@/types"
import type { StudioPage } from "@/types/Studio/StudioPage"
import { getCompletions } from "./autocompletions"
import { getPageNameCompletions } from "./routerScriptPageNames"

const CONFIG_KEYS = [
	{ label: "routerOptions", detail: "passed to createRouter" },
	{ label: "extendRoute", detail: "(route) once per page route" },
	{ label: "setup", detail: "(router) once, before the first navigation" },
]
const ROUTER_OPTION_KEYS = [
	{ label: "scrollBehavior", detail: "(to, from, savedPosition)" },
	{ label: "linkActiveClass", detail: "string" },
	{ label: "linkExactActiveClass", detail: "string" },
	{ label: "parseQuery", detail: "(search) => query" },
	{ label: "stringifyQuery", detail: "(query) => search" },
	{ label: "sensitive", detail: "boolean" },
	{ label: "strict", detail: "boolean" },
	{ label: "end", detail: "boolean" },
]

// Members come from real objects, like page script completions: a vue-router instance built from
// the app's pages, one of its page records, and a resolved location for guard params.
export function routerScriptCompletions(context: CompletionContext, pages: StudioPage[]): CompletionResult | null {
	const titles = pages.flatMap((page) => page.page_title || [])
	return getPageNameCompletions(context, titles) ?? memberCompletions(context, pages) ?? keyCompletions(context)
}

function memberCompletions(context: CompletionContext, pages: StudioPage[]): CompletionResult | null {
	const params = getParamNames(context.state.doc.toString())
	const root = getMemberAccessRoot(context)
	if (!root || !params.all.includes(root)) return null
	return getCompletions(context, getSources(params, pages))
}

function keyCompletions(context: CompletionContext): CompletionResult | null {
	const word = context.matchBefore(/^\s*\w*$/)
	if (!word || (!word.text.trim() && !context.explicit)) return null
	const keys = getKeysForObjectAt(context.state.doc.sliceString(0, context.pos))
	if (!keys) return null
	return {
		from: context.pos - (word.text.match(/\w*$/)?.[0].length ?? 0),
		options: keys.map((key) => ({ ...key, type: "property" })),
		validFor: /^\w*$/,
	}
}

function getSources(params: ReturnType<typeof getParamNames>, pages: StudioPage[]): CompletionSource[] {
	const records = getPageRecords(pages)
	const router = createRouter({ history: createMemoryHistory(), routes: records })
	const location = router.resolve(pages.find((page) => !page.route.includes(":"))?.route || "/")
	const sources = [
		source(params.router, router, "Router"),
		source(params.route, { ...records[0], alias: [], beforeEnter() {} }, "Page route"),
	]
	for (const name of params.locations) sources.push(source(name, location, "Route location"))
	return sources
}

function source(label: string, item: any, detail: string): CompletionSource {
	return { item, completion: { label, type: "variable", detail } }
}

// the records Studio's app router builds, see getPageRoutes in app_router.ts
function getPageRecords(pages: StudioPage[]): RouteRecordRaw[] {
	const records = pages.map((page) => ({
		path: page.route,
		name: page.page_title,
		component: {},
		props: true,
		meta: { pageName: page.name, appRoute: "" },
	}))
	return records.length ? records : [{ path: "/", component: {} }]
}

// `setup(router)`, `extendRoute(route)` and guard params like `beforeEach((to, from) => …)`, by whatever name the script gives them
function getParamNames(code: string) {
	const router = code.match(/\bsetup\s*\(\s*(\w+)/)?.[1] || "router"
	const route = code.match(/\bextendRoute\s*\(\s*(\w+)/)?.[1] || "route"
	const guard =
		/\b(?:beforeEach|beforeResolve|afterEach|beforeEnter)\s*[=(]\s*(?:async\s*)?(?:function\s*\w*\s*)?(?:\(\s*(\w+)(?:\s*,\s*(\w+))?|(\w+)\s*=>)/g
	const locations = new Set(["to", "from"])
	for (const match of code.matchAll(guard)) {
		for (const name of match.slice(1)) if (name) locations.add(name)
	}
	return { router, route, locations: [...locations], all: [router, route, ...locations] }
}

function getMemberAccessRoot(context: CompletionContext): string | null {
	const line = context.state.doc.lineAt(context.pos)
	const before = line.text.slice(0, context.pos - line.from)
	return before.match(/([A-Za-z_$][\w$]*)(?:\.\w*)+$/)?.[1] ?? null
}

// keys belong to the config object itself or to its routerOptions; anywhere else a word is code
function getKeysForObjectAt(textBefore: string) {
	const brace = findEnclosingBrace(textBefore)
	if (brace === -1) return null
	const beforeBrace = textBefore.slice(0, brace)
	if (/\brouterOptions\s*:\s*$/.test(beforeBrace)) return ROUTER_OPTION_KEYS
	if (/(?:^|export\s+default)\s*$/.test(beforeBrace)) return CONFIG_KEYS
	return null
}

function findEnclosingBrace(text: string): number {
	let depth = 0
	for (let index = text.length - 1; index >= 0; index--) {
		if (text[index] === "}") depth++
		if (text[index] === "{" && depth-- === 0) return index
	}
	return -1
}
