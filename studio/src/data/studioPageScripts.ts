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

// page docname -> latest setup fn. Seeded on first import, then refreshed by HMR (see below) so
// navigation always runs the newest code without re-importing — a stable import URL keeps a single
// HMR-accepting module per page instead of accumulating cache-busted copies.
const latestPageSetups: Record<string, PageScriptSetup> = {}

type PageScriptSetup = (...args: any[]) => any

// Invoked when a page script (or a composable/util it imports) hot-updates, with the page's docname
// and freshly hot-loaded setup. studioStore registers this to re-run the active page live.
let pageScriptHotUpdateHandler: ((pageName: string, setup: PageScriptSetup) => void) | null = null
export function setPageScriptHotUpdateHandler(handler: typeof pageScriptHotUpdateHandler) {
	pageScriptHotUpdateHandler = handler
}

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
	// Prefer the latest HMR-refreshed setup so navigating back to a page picks up edits made while
	// it wasn't active (a stable import URL would otherwise hand back the browser-cached original).
	const cached = latestPageSetups[pageName]
	if (cached) return { default: cached }

	const importer = pageScriptImporters.value[pageName]
	if (!importer) return null
	try {
		const mod = await importer()
		if (typeof mod?.default === "function") latestPageSetups[pageName] = mod.default
		return mod
	} catch (err) {
		console.error(`Failed to load page script for ${pageName}:`, err)
		return null
	}
}

// A serve-only Vite transform injects a self-accepting `import.meta.hot` into each exported page
// script that calls this on hot update — passing the page docname (baked in at transform time) and
// the new module, whose transitive imports Vite has already re-fetched fresh. Page scripts load in
// the exported app's own module graph (via dynamic import), so they reach the editor through this
// global rather than the editor's own import.meta.hot.
function applyPageScriptHotUpdate(pageName: string, mod: ModuleNamespace) {
	const setup = mod?.default
	if (typeof setup !== "function") return
	latestPageSetups[pageName] = setup
	pageScriptHotUpdateHandler?.(pageName, setup)
}

if (import.meta.hot) {
	;(window as any).__STUDIO_HMR_applyPageScript = applyPageScriptHotUpdate
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
			// Stable URL (no cache-bust): the page script self-accepts HMR (see applyPageScriptHotUpdate),
			// so Vite keeps a single module per page and refreshes it in place — re-importing with a
			// changing query would fork it into stale copies that each re-run on every edit.
			importers[script.page_name] = () => import(/* @vite-ignore */ script.file_path)
		}
		setPageScriptImporters(importers)
	} catch (err) {
		console.error("Failed to fetch studio page scripts:", err)
	}
}

export function unregisterStudioPageScripts() {
	pageScriptImporters.value = {}
	for (const key in latestPageSetups) delete latestPageSetups[key]
}
