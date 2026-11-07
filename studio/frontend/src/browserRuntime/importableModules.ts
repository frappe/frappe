/**
 * Library modules available to database apps. Reuse the renderer's imports so Vue functions
 * and components have the same identity in application code and the renderer.
 *
 * Each module name must also resolve in an app's Vite build. Additional dependencies require
 * a repository app with npm packages installed; this loader has no CDN fallback.
 *
 * Charts load on demand in a separate chunk. Exclude the full frappe-ui/experimental namespace
 * because it also exports charts and would load them with the other modules. Its components
 * remain available as Studio blocks.
 */

import * as vue from "vue"
import * as vueRouter from "vue-router"
import * as pinia from "pinia"
import * as frappeUI from "frappe-ui"
import * as frappeUIList from "frappe-ui/list"

const modules: Record<string, Record<string, any>> = {
	vue,
	"vue-router": vueRouter,
	pinia,
	"frappe-ui": frappeUI,
	"frappe-ui/list": frappeUIList,
}

const loaders: Record<string, () => Promise<Record<string, any>>> = {
	"frappe-ui/charts": () => import("frappe-ui/charts"),
}

export const IMPORTABLE_MODULES = [...Object.keys(modules), ...Object.keys(loaders)].sort()

const loaded = new Map<string, Promise<Record<string, any>>>()

/**
 * Sucrase uses __esModule to identify module exports. Copy the native namespace and add
 * this flag so default imports are not wrapped a second time.
 */
export function loadImportableModule(specifier: string): Promise<Record<string, any>> {
	let module = loaded.get(specifier)
	if (!module) {
		const namespace = modules[specifier]
		const loader = loaders[specifier]
		if (!namespace && !loader) {
			return Promise.reject(
				new Error(
					`"${specifier}" is not importable here. An app whose files live in the database can ` +
						`import ${IMPORTABLE_MODULES.join(", ")}, and its own files.`,
				),
			)
		}
		module = (namespace ? Promise.resolve(namespace) : loader()).then((resolved) =>
			Object.freeze({ ...resolved, __esModule: true }),
		)
		loaded.set(specifier, module)
	}
	return module
}
