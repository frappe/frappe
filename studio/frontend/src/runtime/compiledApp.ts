/**
 * A database app's sources and the live module registry built from them, shared by the renderer
 * and the editor canvas. Sources come from the DB file store in one call; page scripts arrive
 * with each page and are mounted at the path they occupy in a repository
 * (studio_page/<stem>/<stem>.ts), so their relative imports behave exactly like the files on disk.
 *
 * Nothing imports this module directly — appRuntime.ts loads it on demand, so an app that ships a
 * build never downloads the compiler or the modules it makes importable.
 */

import { createResource } from "frappe-ui"
import { compileFile, describeError } from "@/runtime/compiler"
import { AppModuleRegistry, clearAppStyles } from "@/runtime/moduleRegistry"
import { scrub } from "@/utils/helpers"
import type { RouterConfig } from "@/router/app_router"

interface AppFile {
	path: string
	content: string
	hash: string
}

const appFilesResource = createResource({
	url: "frappe.studio.api.get_app_files",
	method: "GET",
	makeParams: ({ app_name }: { app_name: string }) => ({ app_name }),
})

let loadedAppName: string | null = null
let sources: Record<string, string> = {}
let registry: AppModuleRegistry | null = null

/** Fetch the app's sources and build its registry. The editor and the renderer both call this
 * before anything compiles; calling it again for the same app reuses the loaded registry. */
export async function loadAppRuntime(appName: string): Promise<void> {
	if (loadedAppName === appName && registry) return
	await fetchSources(appName)
}

/** Refetch the sources and rebuild the registry (a file changed, or the editor saved one). */
export async function reloadAppRuntime(): Promise<void> {
	if (!loadedAppName) return
	await fetchSources(loadedAppName)
}

async function fetchSources(appName: string): Promise<void> {
	const files: AppFile[] = await appFilesResource.fetch({ app_name: appName })
	loadedAppName = appName
	sources = {}
	for (const file of files) {
		sources[file.path] = file.content
	}
	registry = new AppModuleRegistry(sources)
	clearAppStyles(new Set(Object.keys(sources)))
}

/** Drop the loaded app (the editor switched to a repository app). */
export function unloadAppRuntime(): void {
	loadedAppName = null
	sources = {}
	registry = null
	clearAppStyles()
}

export function getAppSource(path: string): string | undefined {
	return sources[path]
}

export function loadAppModule(path: string): Promise<any> {
	return getRegistry().loadModule(path)
}

/** The app's router config from its stored router.ts, if it has one. */
export async function loadAppRouterConfig(): Promise<RouterConfig | undefined> {
	const registry = getRegistry()
	const routerFile = ["router.ts", "router.js"].find((path) => registry.hasFile(path))
	if (!routerFile) return undefined
	const module = await registry.loadModule(routerFile)
	return module?.default || undefined
}

/** Mount the page's script at the path it occupies in a repository and load it; its default
 * export is setup(). */
export async function loadAppPageScriptModule(page: {
	page_title?: string
	script?: string | null
}): Promise<Record<string, any> | null> {
	const script = page.script || ""
	if (!script.trim()) return null
	const stem = scrub(page.page_title || "page")
	const path = `studio_page/${stem}/${stem}.ts`
	const registry = getRegistry()
	await registry.addFile(path, script)
	return registry.loadModule(path)
}

function getRegistry(): AppModuleRegistry {
	if (!registry) throw new Error("No Studio app runtime is loaded.")
	return registry
}

/** Syntax-check a page script (a TypeScript module) before saving; null when it parses. */
export async function checkAppScript(source: string): Promise<string | null> {
	const compiled = await compileFile("page_script.ts", source)
	return compiled.errors.length ? compiled.errors.map(describeError).join("\n") : null
}
