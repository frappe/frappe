import { shallowRef } from "vue"
import { createResource } from "frappe-ui"

type ModuleNamespace = Record<string, any>
type PageScriptImporter = () => Promise<ModuleNamespace>

export const studioPageScriptsResource = createResource({
	url: "studio.api.get_studio_page_scripts",
	makeParams: ({ frappe_app }: { frappe_app: string }) => {
		return {
			frappe_app: frappe_app,
		}
	},
})

// page docname -> lazy importer of its compiled `setup()` module (the chunk loads on demand)
const pageScriptImporters = shallowRef<Record<string, PageScriptImporter>>({})

/**
 * Register the available page-script importers. The dev/editor path builds these from filesystem
 * discovery (Vite-served); the production per-app build entry calls this with its code-split
 * chunks. Either way the importer is lazy — nothing downloads until loadPageScriptModule() runs it.
 */
export function setPageScriptImporters(importers: Record<string, PageScriptImporter>) {
	pageScriptImporters.value = importers
}

/** Whether a compiled page script exists for this page (i.e. the page is in code mode). */
export function hasPageScript(pageName: string): boolean {
	return Boolean(pageScriptImporters.value[pageName])
}

/** Load a page's compiled module; its default export is the `setup()` function. */
export async function loadPageScriptModule(pageName: string): Promise<ModuleNamespace | null> {
	const importer = pageScriptImporters.value[pageName]
	if (!importer) return null
	try {
		return await importer()
	} catch (err) {
		console.error(`Failed to load page script for ${pageName}:`, err)
		return null
	}
}

/**
 * Dev/editor: discover exported <page>.ts files and register their importers (served live by the
 * Vite dev server). Production reuses setPageScriptImporters from the per-app build entry instead.
 */
export async function registerStudioPageScripts(frappeApp: string): Promise<void> {
	if (!frappeApp) return
	try {
		const scripts: { page_name: string; file_path: string }[] =
			await studioPageScriptsResource.reload({ frappe_app: frappeApp })
		const importers: Record<string, PageScriptImporter> = {}
		for (const script of scripts) {
			// Cache-bust per load so re-running setPageScript after an edit picks up the new file;
			// the ES module cache would otherwise return the stale module. Dev-only path (prod uses
			// the built bundle via setPageScriptImporters), so re-transforming each load is fine.
			importers[script.page_name] = () =>
				import(/* @vite-ignore */ `${script.file_path}?t=${Date.now()}`)
		}
		setPageScriptImporters(importers)
	} catch (err) {
		console.error("Failed to fetch studio page scripts:", err)
	}
}

export function unregisterStudioPageScripts() {
	pageScriptImporters.value = {}
}
