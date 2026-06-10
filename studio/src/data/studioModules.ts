import { shallowRef } from "vue"
import { createResource } from "frappe-ui"
import type { StudioModuleMeta } from "@/types/StudioModule"

export const studioModulesResource = createResource({
	url: "studio.api.get_studio_modules",
	makeParams: ({ frappe_app }: { frappe_app: string }) => {
		return {
			frappe_app: frappe_app,
		}
	},
})

type ModuleNamespace = Record<string, any>
type ModuleImporter = () => Promise<ModuleNamespace>

// module_path -> lazy importer (the chunk only downloads/executes when called)
const moduleImporters = shallowRef<Record<string, ModuleImporter>>({})
// module_path -> resolved binding group { bindingName: value }, populated on demand
export const studioModulesRegistry = shallowRef<Record<string, ModuleNamespace>>({})

/** Flatten a module namespace into bindings: named exports by name, default export by file name. */
export function flattenModule(ns: ModuleNamespace, moduleName: string): ModuleNamespace {
	const group: ModuleNamespace = {}
	for (const [exportName, value] of Object.entries(ns)) {
		group[exportName === "default" ? moduleName : exportName] = value
	}
	return group
}

function moduleNameFromPath(modulePath: string): string {
	const base = modulePath.split("/").pop() || modulePath
	return base.replace(/\.(js|ts)$/, "")
}

/**
 * Register the available module importers. The dev/editor path builds these from filesystem
 * discovery; the production per-app build entry calls this with its code-split chunks. Either
 * way the importer is lazy — nothing downloads until loadModules() runs it.
 */
export function setModuleImporters(importers: Record<string, ModuleImporter>) {
	moduleImporters.value = importers
}

/**
 * Load the given module paths into the registry (idempotent). App-scope modules are loaded
 * eagerly before the first render; page-scope modules are loaded lazily on navigation, so a
 * heavy module attached to one page isn't downloaded on the others.
 */
export async function loadModules(paths: string[]): Promise<void> {
	const toLoad = (paths || []).filter(
		(path) => !studioModulesRegistry.value[path] && moduleImporters.value[path],
	)
	if (!toLoad.length) return

	const loaded = await Promise.all(
		toLoad.map(async (path) => {
			try {
				const ns = await moduleImporters.value[path]()
				return [path, flattenModule(ns, moduleNameFromPath(path))] as const
			} catch (err) {
				console.error(`Failed to load studio module ${path}:`, err)
				return null
			}
		}),
	)

	// single reassignment so parallel loads don't clobber each other (shallowRef)
	const next = { ...studioModulesRegistry.value }
	for (const entry of loaded) {
		if (entry) next[entry[0]] = entry[1]
	}
	studioModulesRegistry.value = next
}

/**
 * Dev/editor: discover modules and register their importers (served live by the Vite dev
 * server). Production reuses setModuleImporters from the per-app build entry instead.
 */
export async function registerStudioModules(frappeApp: string): Promise<StudioModuleMeta[]> {
	if (!frappeApp) return []
	try {
		const modules: StudioModuleMeta[] = await studioModulesResource.reload({ frappe_app: frappeApp })
		const importers: Record<string, ModuleImporter> = {}
		for (const mod of modules) {
			importers[mod.module_path] = () => import(/* @vite-ignore */ mod.file_path)
		}
		setModuleImporters(importers)
		return modules
	} catch (err) {
		console.error("Failed to fetch studio modules:", err)
		return []
	}
}

export function unregisterStudioModules() {
	moduleImporters.value = {}
	studioModulesRegistry.value = {}
}
