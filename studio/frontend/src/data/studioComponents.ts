import { createListResource } from "frappe-ui"
import type { StudioComponent } from "@/runtime/types/Studio/StudioComponent"

const studioComponents = createListResource({
	method: "GET",
	doctype: "Studio Component",
	fields: ["name", "component_id", "component_name", "studio_app", "creation", "modified"],
	filters: {
		"is_disabled": 0,
	},
	cache: "studio-components",
	orderBy: "creation asc",
	pageLength: 50,
	// an app's own component hides a global one with the same id
	transform(components: StudioComponent[]) {
		const appComponentIds = new Set(
			components.filter((component) => component.studio_app).map((component) => component.component_id),
		)
		return components.filter(
			(component) => component.studio_app || !appComponentIds.has(component.component_id),
		)
	},
})

/** List the components that an app can use: its own, and the global ones. */
function loadStudioComponents(studioApp: string) {
	studioComponents.filters = { is_disabled: 0, studio_app: ["in", [studioApp, ""]] }
	return studioComponents.reload()
}

export { studioComponents, loadStudioComponents }
