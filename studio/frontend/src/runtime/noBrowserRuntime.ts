/**
 * What `@/runtime/appRuntime` resolves to inside a per-app Vite build (see src/scripts/build.js).
 *
 * A built app's `.vue` components and page scripts are compiled by that build, so nothing in it
 * ever compiles in the browser. Aliasing the runtime away here keeps the compilers, and the
 * modules they make importable, out of every app bundle.
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
