import { defineAsyncComponent, shallowRef } from "vue"
import { vueComponents } from "@/data/vueComponents"
import type { CustomVueComponentMeta } from "@/types/vue"

export const customVueComponentsRegistry = shallowRef<Record<string, any>>({})
/**
 * Dynamically register the custom Vue components one studio app exports into the registry.
 */
export async function registerCustomVueComponents(
	frappeApp: string,
	studioApp: string,
	registeredComponents: Record<string, any> = {},
): Promise<CustomVueComponentMeta[]> {
	try {
		if (!frappeApp || !studioApp) return []
		const components: CustomVueComponentMeta[] = await vueComponents.reload({
			frappe_app: frappeApp,
			studio_app: studioApp,
		})

		const registry = { ...customVueComponentsRegistry.value }
		for (const comp of components) {
			try {
				const asyncComp = defineAsyncComponent(() => import(/* @vite-ignore */ comp.file_path))
				registry[comp.component_name] = asyncComp
				registeredComponents[comp.component_name] = asyncComp
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
export function unregisterCustomVueComponents(
	components: CustomVueComponentMeta[],
	registeredComponents: Record<string, any> = {},
) {
	const registry = { ...customVueComponentsRegistry.value }
	for (const comp of components) {
		delete registry[comp.component_name]
		delete registeredComponents[comp.component_name]
	}
	customVueComponentsRegistry.value = registry
}

// Re-sync the registry to the app's current custom components. register() only merges, so on its
// own a removed component would linger; this also evicts any that no longer exist. Pass an empty
// frappeApp to clear them all (e.g. a non-standard app). Shared by the editor and the preview.
export async function reloadCustomVueComponents(
	frappeApp: string,
	studioApp: string,
	registeredComponents: Record<string, any> = {},
): Promise<CustomVueComponentMeta[]> {
	const before = Object.keys(customVueComponentsRegistry.value)
	const components = await registerCustomVueComponents(frappeApp, studioApp, registeredComponents)

	const current = new Set(components.map((comp) => comp.component_name))
	const removed = before.filter((name) => !current.has(name)).map((name) => ({ component_name: name }))
	if (removed.length) unregisterCustomVueComponents(removed as CustomVueComponentMeta[], registeredComponents)

	return components
}
