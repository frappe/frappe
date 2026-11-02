import { defineAsyncComponent, shallowRef } from "vue"
import { vueComponents } from "@/data/vueComponents"
import type { CustomVueComponentMeta } from "@/types/vue"

export const customVueComponentsRegistry = shallowRef<Record<string, any>>({})
/**
 * Dynamically register custom Vue components from a specific Frappe app into the custom components registry.
 * @param frappeApp - The Frappe app name to fetch components from
 */
export async function registerCustomVueComponents(frappeApp: string): Promise<CustomVueComponentMeta[]> {
	try {
		if (!frappeApp) return []
		const components: CustomVueComponentMeta[] = await vueComponents.reload({ frappe_app: frappeApp })

		const registry = { ...customVueComponentsRegistry.value }
		for (const comp of components) {
			try {
				const asyncComp = defineAsyncComponent(() => import(/* @vite-ignore */ comp.file_path))
				registry[comp.component_name] = asyncComp
				if (window.__APP_COMPONENTS__) {
					window.__APP_COMPONENTS__[comp.component_name] = asyncComp
				}
			} catch (err) {
				console.error(`Failed to load custom component ${comp.component_name}:`, err)
			}
		}
		customVueComponentsRegistry.value = registry
		return components
	} catch (err) {
		console.error("Failed to fetch custom Vue components:", err)
		return []
	}
}

/**
 * Unregister previously registered custom Vue components from the custom components registry.
 * Called when switching apps to clean up components from the previous app's frappe_app.
 */
export function unregisterCustomVueComponents(components: CustomVueComponentMeta[]) {
	const registry = { ...customVueComponentsRegistry.value }
	for (const comp of components) {
		delete registry[comp.component_name]
		if (window.__APP_COMPONENTS__) {
			delete window.__APP_COMPONENTS__[comp.component_name]
		}
	}
	customVueComponentsRegistry.value = registry
}

// Re-sync the registry to the app's current custom components. register() only merges, so on its
// own a removed component would linger; this also evicts any that no longer exist. Pass an empty
// frappeApp to clear them all (e.g. a non-standard app). Shared by the editor and the preview.
export async function reloadCustomVueComponents(frappeApp: string): Promise<CustomVueComponentMeta[]> {
	const before = Object.keys(customVueComponentsRegistry.value)
	const components = await registerCustomVueComponents(frappeApp)

	const current = new Set(components.map((comp) => comp.component_name))
	const removed = before.filter((name) => !current.has(name)).map((name) => ({ component_name: name }))
	if (removed.length) unregisterCustomVueComponents(removed as CustomVueComponentMeta[])

	return components
}
