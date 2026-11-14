/**
 * Replace @/browserRuntime/appRuntime in app builds through the alias in src/scripts/build.js.
 *
 * Built apps already contain compiled components and page scripts. These exports let shared
 * renderer code import the runtime API without including the browser compiler or registry.
 */

function notBuiltForThisApp(): never {
	throw new Error("This app's files are compiled by its build, not in the browser.")
}

export const loadAppRuntime = notBuiltForThisApp
export const loadAppRouterConfig = notBuiltForThisApp
export const compilePageScript = notBuiltForThisApp
export const checkAppScript = notBuiltForThisApp

export async function reloadAppRuntime(): Promise<void> {}
export async function unloadAppRuntime(): Promise<void> {}
