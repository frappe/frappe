/**
 * The bare modules a database app may import — the renderer's own copies, so the app's `ref` or
 * `Button` is the same instance the page around it uses.
 *
 * Every specifier here must also resolve in a real Vite build, so an app that moves to a
 * repository keeps building. Anything else is the signal to move the app to a repository, where
 * npm is available; there is no CDN escape hatch, and that closed list is the supply-chain
 * boundary.
 *
 * All but one are modules the renderer already ships, so they are imported here rather than
 * fetched: offering them cannot grow any app's bundle. The chart family is the exception — the
 * editor loads it on demand, so it keeps its own chunk here too. `frappe-ui/experimental` is
 * deliberately absent: it re-exports the charts, so offering that namespace whole would pull
 * them into every bundle. Its components are available as blocks.
 */

import * as vue from "vue"
import * as vueRouter from "vue-router"
import * as pinia from "pinia"
import * as vueuse from "@vueuse/core"
import * as frappeUI from "frappe-ui"
import * as frappeUIList from "frappe-ui/list"

const modules: Record<string, Record<string, any>> = {
	vue,
	"vue-router": vueRouter,
	pinia,
	"@vueuse/core": vueuse,
	"frappe-ui": frappeUI,
	"frappe-ui/list": frappeUIList,
}

const loaders: Record<string, () => Promise<Record<string, any>>> = {
	"frappe-ui/charts": () => import("frappe-ui/charts"),
}

export const IMPORTABLE_MODULES = [...Object.keys(modules), ...Object.keys(loaders)].sort()

const loaded = new Map<string, Promise<Record<string, any>>>()

/**
 * A namespace object carries no __esModule flag, so sucrase's default-import interop would
 * wrap it again; copy it and mark it.
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
