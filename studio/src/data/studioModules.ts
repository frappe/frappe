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

// module_name -> the module's binding: its `default` export if present, else the
// namespace of named exports. Composables/stores/utilities all flow through here.
export const studioModulesRegistry = shallowRef<Record<string, any>>({})

/**
 * Dynamically import custom JS/TS modules from a Frappe app and register them.
 * Dev/editor path: modules are imported live via the Vite dev server. In production
 * the per-app build provides them on window.__APP_MODULES__ instead.
 */
export async function registerStudioModules(frappeApp: string): Promise<StudioModuleMeta[]> {
	if (!frappeApp) return []
	try {
		const modules: StudioModuleMeta[] = await studioModulesResource.reload({ frappe_app: frappeApp })
		const registry: Record<string, any> = {}
		await Promise.all(
			modules.map(async (mod) => {
				try {
					const imported = await import(/* @vite-ignore */ mod.file_path)
					for (const [exportName, value] of Object.entries(imported)) {
						const bindingName = exportName === "default" ? mod.module_name : exportName
						registry[bindingName] = value
					}
				} catch (err) {
					console.error(`Failed to load studio module ${mod.module_name}:`, err)
				}
			}),
		)
		studioModulesRegistry.value = registry
		return modules
	} catch (err) {
		console.error("Failed to fetch studio modules:", err)
		return []
	}
}

export function unregisterStudioModules() {
	studioModulesRegistry.value = {}
}
