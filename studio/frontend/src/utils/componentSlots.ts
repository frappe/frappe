import components from "@/data/components"
import { componentFolders } from "@/utils/components"
import { reactive } from "vue"
import type { CustomVueComponentMeta } from "@/types/vue"

// ?raw to get raw content of a file as string
const frappeUIModules: Record<string, string> = import.meta.glob(
	[
		"../../node_modules/frappe-ui/src/components/**/*.vue",
		"../../node_modules/frappe-ui/src/molecules/**/*.vue",
		"../../node_modules/frappe-ui/experimental/**/*.vue",
		"../../node_modules/frappe-ui/src/charts/*.vue",
		"!**/experimental/Charts/**",
		"!**/*.story.vue",
		"!**/stories/**",
	],
	{ query: "?raw", eager: true, import: "default" },
)

const studioModules: Record<string, string> = import.meta.glob("@/components/AppLayout/*.vue", {
	query: "?raw",
	eager: true,
	import: "default",
})

// @framework/ui component sources (apps/frappe/ui). Used for slot parsing.
const frameworkUIModules: Record<string, string> = import.meta.glob(
	["../../../../../frappe/ui/src/components/**/*.vue", "!**/*.story.vue"],
	{ query: "?raw", eager: true, import: "default" },
)

// Component name -> "<Folder>/<File>.vue" under apps/frappe/ui/src/components.
// The folder often differs from the component name (Notifications, ActivityTimeline,
// ListView, FileUpload group several components each).
const frameworkUIComponentPaths: Record<string, string> = {
	FormLayout: "FormLayout/FormLayout.vue",
	Link: "Link/Link.vue",
	Grid: "Grid/Grid.vue",
	Phone: "Phone/Phone.vue",
	TableMultiSelect: "TableMultiSelect/TableMultiSelect.vue",
	NotificationPanel: "Notifications/NotificationPanel.vue",
	NotificationItem: "Notifications/NotificationItem.vue",
	ActivityTimeline: "ActivityTimeline/ActivityTimeline.vue",
	EmailItem: "ActivityTimeline/EmailItem.vue",
	CommentItem: "ActivityTimeline/CommentItem.vue",
	EmailComposer: "Composer/EmailComposer/EmailComposer.vue",
	CommentComposer: "Composer/CommentComposer/CommentComposer.vue",
	Filter: "Filter/Filter.vue",
	SortBy: "SortBy/SortBy.vue",
	QuickFilter: "QuickFilter/QuickFilter.vue",
	ColumnSettings: "ColumnSettings/ColumnSettings.vue",
	ListViewShell: "ListView/ListViewShell.vue",
	FileUploadDialog: "FileUpload/FileUploadDialog.vue",
	AttachmentsList: "FileUpload/AttachmentsList.vue",
	UploadTray: "FileUpload/UploadTray.vue",
}

const templateCache = new Map<string, string>()

const customComponentFilePaths = new Map<string, string>()

async function registerCustomComponentPaths(components: CustomVueComponentMeta[]) {
	const previousPaths = new Map(customComponentFilePaths)
	customComponentFilePaths.clear()
	for (const comp of components) {
		customComponentFilePaths.set(comp.component_name, comp.file_path)
	}
	for (const [name, filePath] of previousPaths) {
		if (customComponentFilePaths.get(name) !== filePath) invalidateComponentCache(name)
	}
	await Promise.all(components.map((comp) => getComponentSlots(comp.component_name, true)))
}

function getComponentTemplate(componentName: string): string {
	if (templateCache.has(componentName)) {
		return templateCache.get(componentName) || ""
	}

	let rawTemplate = ""

	if (components.isFrappeUIComponent(componentName)) {
		rawTemplate = resolveFrappeUITemplate(componentName)
	} else if (components.isFrameworkUIComponent(componentName)) {
		const relativePath = frameworkUIComponentPaths[componentName]
		if (relativePath) {
			const modulePath = `../../../../../frappe/ui/src/components/${relativePath}`
			if (frameworkUIModules[modulePath]) {
				rawTemplate = frameworkUIModules[modulePath]
			}
		}
	} else {
		const modulePath = `/src/components/AppLayout/${componentName}.vue`
		if (studioModules[modulePath]) {
			rawTemplate = studioModules[modulePath]
		}
	}

	const template = rawTemplate || ""
	if (template) {
		templateCache.set(componentName, template)
	}
	return template
}

// Resolve a frappe-ui component's raw .vue source. Tries the flat components path,
// then a component folder, then a filename scan across the glob. The scan covers
// cases where the file name doesn't drive the path: molecules under
// molecules/<family>/ (List family) and grouped families whose parts share one
// folder (SettingsDialog/SettingsRow.vue, …).
function resolveFrappeUITemplate(componentName: string): string {
	const base = "../../node_modules/frappe-ui/src"
	const folderName = componentFolders[componentName] || componentName
	const candidates = [
		`${base}/components/${componentName}.vue`,
		`${base}/components/${folderName}/${componentName}.vue`,
	]
	for (const path of candidates) {
		if (frappeUIModules[path]) return frappeUIModules[path]
	}
	return findModuleByFileName(frappeUIModules, componentName)
}

function findModuleByFileName(modules: Record<string, string>, componentName: string): string {
	const suffix = `/${componentName}.vue`
	const match = Object.keys(modules).find((path) => path.endsWith(suffix))
	return match ? modules[match] : ""
}

async function fetchCustomComponentTemplate(componentName: string): Promise<string> {
	if (templateCache.has(componentName)) {
		return templateCache.get(componentName) || ""
	}

	const filePath = customComponentFilePaths.get(componentName)
	if (!filePath) return ""

	try {
		// Use Vite's ?raw import to get unprocessed file content as a string. In dev, a unique
		// query busts the browser's ES-module cache so a re-fetch after invalidateComponentCache
		// (HMR content edit) gets the new source instead of the stale cached module.
		const cacheBust = import.meta.env.DEV ? `&t=${Date.now()}` : ""
		const module = await import(/* @vite-ignore */ `${filePath}?raw${cacheBust}`)
		return module.default || ""
	} catch (error) {
		console.error(`Error fetching custom component template ${componentName}:`, error)
		return ""
	}
}

function parseSlotsFromTemplate(template: string) {
	const slots = new Map<string, { name: string; type: "named" | "default" }>()

	for (const [, attributes] of template.matchAll(/<slot\b([^>]*)>/gi)) {
		// `<slot :name="…">` is a dynamic forwarder (e.g. Link → Combobox), not a real
		// default slot — skip it rather than misreading the missing static name as "default"
		if (/:name\s*=/i.test(attributes)) continue
		const named = attributes.match(/(?:^|\s)name\s*=\s*["']([^"']*)["']/i)
		const name = named?.[1] || "default"
		if (!slots.has(name)) {
			slots.set(name, { name, type: named ? "named" : "default" })
		}
	}
	return [...slots.values()]
}

const slotsCache = reactive(new Map<string, ReturnType<typeof parseSlotsFromTemplate>>())

async function getComponentSlots(componentName: string, isCustomVueComponent?: boolean) {
	const cached = slotsCache.get(componentName)
	if (cached) return cached
	const filePath = customComponentFilePaths.get(componentName)
	const template = isCustomVueComponent
		? await fetchCustomComponentTemplate(componentName)
		: getComponentTemplate(componentName)
	if (isCustomVueComponent && customComponentFilePaths.get(componentName) !== filePath) return []
	const slots = parseSlotsFromTemplate(template)
	if (template) {
		if (isCustomVueComponent) templateCache.set(componentName, template)
		slotsCache.set(componentName, slots)
	}
	return slots
}

function componentHasDefaultSlot(componentName: string): boolean {
	if (!slotsCache.has(componentName)) {
		const template = getComponentTemplate(componentName)
		if (template) slotsCache.set(componentName, parseSlotsFromTemplate(template))
	}
	return (slotsCache.get(componentName) ?? []).some((slot) => slot.type === "default")
}

function invalidateComponentCache(componentName: string) {
	templateCache.delete(componentName)
	slotsCache.delete(componentName)
}

export {
	getComponentTemplate,
	getComponentSlots,
	componentHasDefaultSlot,
	invalidateComponentCache,
	registerCustomComponentPaths,
}
