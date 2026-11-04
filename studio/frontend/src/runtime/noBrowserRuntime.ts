/**
 * Replace @/runtime/appRuntime in app builds through the alias in src/scripts/build.js.
 *
 * Built apps already contain compiled components and page scripts. These exports let shared
 * renderer code import the runtime API without including the browser compiler or registry.
 */

function notBuiltForThisApp(): never {
	throw new Error("This app's files are compiled by its build, not in the browser.")
}

export const loadAppRuntime = notBuiltForThisApp
export const loadAppModule = notBuiltForThisApp
export const loadAppRouterConfig = notBuiltForThisApp
export const loadAppPageScriptModule = notBuiltForThisApp
export const checkAppScript = notBuiltForThisApp

export async function reloadAppRuntime(): Promise<void> {}
export async function unloadAppRuntime(): Promise<void> {}
export async function getAppSource(): Promise<string | undefined> {
	return undefined
}
