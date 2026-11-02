/**
 * The browser runtime for a database app's source files, loaded on demand.
 *
 * Everything behind this module — the SFC/TypeScript compilers and the modules an app may import
 * — is heavy and only a database app needs it, so it stays out of the editor's and the renderer's
 * own bundles. Each call here loads that chunk first; `unloadAppRuntime` does not, so an app that
 * never compiles anything never pays for it.
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

/** Syntax-check a page script (a TypeScript module) before saving; null when it parses. */
export async function checkAppScript(source: string): Promise<string | null> {
	return (await compiledApp()).checkAppScript(source)
}
