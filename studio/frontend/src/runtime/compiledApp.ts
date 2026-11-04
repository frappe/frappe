/**
 * Manage database source files and their module registry for the editor and default renderer.
 *
 * Fetch stored files together. Page scripts arrive with their page data and use the virtual
 * path studio_page/<stem>/<stem>.ts, so relative imports resolve as they do in a repository.
 * appRuntime.ts loads this implementation on demand; app builds exclude it.
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

/** Fetch source and create a registry, or reuse the registry already loaded for this app. */
export async function loadAppRuntime(appName: string): Promise<void> {
	if (loadedAppName === appName && registry) return
	await fetchSources(appName)
}

/** Fetch updated source and replace the loaded app's registry. */
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

/** Clear the loaded app's source, registry and styles. */
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

/** Load router.ts or router.js and return its config, if present. */
export async function loadAppRouterConfig(): Promise<RouterConfig | undefined> {
	const registry = getRegistry()
	const routerFile = ["router.ts", "router.js"].find((path) => registry.hasFile(path))
	if (!routerFile) return undefined
	const module = await registry.loadModule(routerFile)
	return module?.default || undefined
}

/** Load a page script at the path used by repository apps. Its default export is setup(). */
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

/** Return a page script's syntax error, or null if the TypeScript module parses. */
export async function checkAppScript(source: string): Promise<string | null> {
	const compiled = await compileFile("page_script.ts", source)
	return compiled.errors.length ? compiled.errors.map(describeError).join("\n") : null
}
