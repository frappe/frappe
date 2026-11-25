import { call } from "frappe-ui"

type ModuleNamespace = Record<string, any>
type ComponentScriptImporter = () => Promise<ModuleNamespace>
type HotUpdateListener = (componentId: string, module: ModuleNamespace) => void

// component id -> lazy importer of its script module. The editor of a repository app gets these
// from the Vite dev server, and an app build from its own chunks.
let componentScriptImporters: Record<string, ComponentScriptImporter> = {}

// component id -> the module from its last hot update. The import URL stays the same, so importing
// again returns the module the browser cached first.
const hotUpdatedModules: Record<string, ModuleNamespace> = {}

const hotUpdateListeners = new Set<HotUpdateListener>()

export function setComponentScriptImporters(importers: Record<string, ComponentScriptImporter>) {
	componentScriptImporters = importers
}

export function unregisterStudioComponentScripts() {
	componentScriptImporters = {}
	for (const componentId in hotUpdatedModules) delete hotUpdatedModules[componentId]
}

export function hasBuiltComponentScript(componentId: string): boolean {
	return Boolean(componentScriptImporters[componentId])
}

export async function loadBuiltComponentScript(componentId: string): Promise<ModuleNamespace> {
	return hotUpdatedModules[componentId] ?? componentScriptImporters[componentId]()
}

export function onComponentScriptHotUpdate(listener: HotUpdateListener) {
	hotUpdateListeners.add(listener)
	return () => hotUpdateListeners.delete(listener)
}

/** Register the script files that a repository app exports, as the Vite dev server serves them. */
export async function registerStudioComponentScripts(frappeApp: string, studioApp: string): Promise<void> {
	let scripts: { component_id: string; file_path: string }[] = []
	try {
		scripts = await call("frappe.studio.api.get_studio_component_scripts", {
			frappe_app: frappeApp,
			studio_app: studioApp,
		})
	} catch (error) {
		console.error("Failed to fetch studio component scripts:", error)
	}
	setComponentScriptImporters(
		Object.fromEntries(
			scripts.map((script) => [script.component_id, () => import(/* @vite-ignore */ script.file_path)]),
		),
	)
}

// studioFolderWatcher.js makes each component script accept its own hot updates and call this.
if (import.meta.hot) {
	;(window as any).__STUDIO_HMR_applyComponentScript = (componentId: string, module: ModuleNamespace) => {
		hotUpdatedModules[componentId] = module
		hotUpdateListeners.forEach((listener) => listener(componentId, module))
	}
}
