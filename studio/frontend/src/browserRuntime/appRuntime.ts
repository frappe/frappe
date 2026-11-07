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
	return import("@/browserRuntime/compiledApp")
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

export async function loadAppRouterConfig(): Promise<RouterConfig | undefined> {
	return (await compiledApp()).loadAppRouterConfig()
}

export async function loadAppPageScriptModule(page: {
	page_title?: string
	script?: string | null
}): Promise<Record<string, any> | null> {
	return (await compiledApp()).loadAppPageScriptModule(page)
}

/** Return a page script's syntax error, or null if the module parses. */
export async function checkAppScript(
	source: string,
	filename = "page_script.js",
	databaseApp = false,
): Promise<string | null> {
	return (await compiledApp()).checkAppScript(source, filename, databaseApp)
}
