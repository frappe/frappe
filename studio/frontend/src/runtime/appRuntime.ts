/**
 * Load the browser source compiler and module registry on demand.
 *
 * Keep the compilers and available library namespaces out of the initial editor and renderer
 * bundles. Compilation or syntax checking loads them when needed. Reading or unloading an
 * unused runtime does not load them. App builds use noBrowserRuntime.ts instead.
 */

import type { RouterConfig } from "@/router/app_router"

let loaded = false

function compiledApp() {
	loaded = true
	return import("@/runtime/compiledApp")
}

export async function loadAppRuntime(appName: string): Promise<void> {
	return (await compiledApp()).loadAppRuntime(appName)
}

export async function reloadAppRuntime(): Promise<void> {
	if (!loaded) return
	return (await compiledApp()).reloadAppRuntime()
}

export async function unloadAppRuntime(): Promise<void> {
	if (!loaded) return
	return (await compiledApp()).unloadAppRuntime()
}

export async function getAppSource(path: string): Promise<string | undefined> {
	if (!loaded) return undefined
	return (await compiledApp()).getAppSource(path)
}

export async function loadAppModule(path: string): Promise<any> {
	return (await compiledApp()).loadAppModule(path)
}

export async function loadAppRouterConfig(): Promise<RouterConfig | undefined> {
	return (await compiledApp()).loadAppRouterConfig()
}

export async function loadAppPageScriptModule(page: {
	page_title?: string
	script?: string | null
}): Promise<Record<string, any> | null> {
	return (await compiledApp()).loadAppPageScriptModule(page)
}

/** Return a page script's syntax error, or null if the TypeScript module parses. */
export async function checkAppScript(source: string): Promise<string | null> {
	return (await compiledApp()).checkAppScript(source)
}
