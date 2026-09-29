import router from "@/router/studio_router"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import { openInDesk, openPageInDesk } from "@/utils/helpers"
import { createRegistry, type RegistryItem } from "@/utils/createRegistry"
import { nextTick } from "vue"

/** A key binding for a command. The description labels it in the shortcuts dialog. */
export type CommandKeys = {
	/** a frappe-ui combo such as "Mod+Shift+K" */
	combo: string
	allowInInput?: boolean
	description: string
}

export type Command = RegistryItem & {
	/** a function when the label depends on state, such as Show or Hide Left Panel */
	title: string | (() => string)
	icon: string | (() => string)
	group: CommandGroup
	action: () => void
	keys?: CommandKeys
	/** keep the palette open, for a command that opens a step */
	keepOpen?: boolean
}

export const commandGroups = ["Navigate", "Page", "Layers", "View", "General"] as const
export type CommandGroup = (typeof commandGroups)[number]

export const resolveText = (value: string | (() => string)) => (typeof value === "function" ? value() : value)

// the page route chunk imports this after pinia is installed, so the lookups resolve
const store = useStudioStore()
const canvasStore = useCanvasStore()

export const commands = createRegistry<Command>()

/**
 * Every command that declares a binding, shaped for useKeyboardShortcut. Read once at
 * setup, so a command registered later gets no binding until the next reload.
 */
export function commandShortcuts() {
	return commands.all.value
		.filter((command) => command.keys)
		.map((command) => ({
			...command.keys!,
			group: command.group,
			enabled: command.condition,
			handler: () => {
				store.componentContextMenu?.hideContextMenu()
				command.action()
			},
		}))
}

// Navigate

commands.register({
	name: "go-to-dashboard",
	title: "Go to Dashboard",
	icon: "lucide-layout-dashboard",
	group: "Navigate",
	action: () => router.push({ name: "Home" }),
})

commands.register({
	name: "view-app-in-desk",
	title: "View App in Desk",
	icon: "lucide-arrow-up-right",
	group: "Navigate",
	condition: () => Boolean(store.activeApp),
	action: () => openInDesk(store.activeApp!),
})

commands.register({
	name: "view-page-in-desk",
	title: "View Page in Desk",
	icon: "lucide-arrow-up-right",
	group: "Navigate",
	condition: () => Boolean(store.activePage),
	action: () => openPageInDesk(store.activePage!),
})

// Page

commands.register({
	name: "preview-page",
	title: "Preview Page",
	icon: "lucide-play",
	group: "Page",
	condition: () => Boolean(store.activeApp && store.activePage),
	action: () => store.openPageInBrowser(store.activeApp!, store.activePage!, true),
})

commands.register({
	name: "publish-page",
	title: "Publish Page",
	icon: "lucide-globe",
	group: "Page",
	// like the publish button: a fragment has to be saved or closed first
	condition: () => Boolean(store.activePage) && !canvasStore.showFragmentCanvas,
	action: () => store.publishPage(),
})

commands.register({
	name: "page-options",
	title: "Page Options",
	icon: "lucide-file-cog",
	group: "Page",
	condition: () => Boolean(store.activePage),
	action: () => (store.showPageOptions = true),
})

// Layers

const showLayersTab = async () => {
	store.studioLayout.showLeftPanel = true
	store.studioLayout.leftPanelActiveTab = "Layers"
	await nextTick()
}

commands.register({
	name: "expand-layers",
	title: "Expand All Layers",
	icon: "lucide-chevrons-up-down",
	group: "Layers",
	action: async () => {
		await showLayersTab()
		store.activeLayers?.expandAll()
	},
})

commands.register({
	name: "collapse-layers",
	title: "Collapse All Layers",
	icon: "lucide-chevrons-down-up",
	group: "Layers",
	action: async () => {
		await showLayersTab()
		store.activeLayers?.collapseAll()
	},
})

// View

commands.register({
	name: "toggle-panels",
	// both panels follow the right one, so its state names the action
	title: () => (store.studioLayout.showRightPanel ? "Hide Panels" : "Show Panels"),
	icon: "lucide-panels-left-bottom",
	group: "View",
	keys: { combo: "Mod+Backslash", description: "Toggle Panels" },
	action: () => {
		store.studioLayout.showRightPanel = !store.studioLayout.showRightPanel
		store.studioLayout.showLeftPanel = store.studioLayout.showRightPanel
	},
})

commands.register({
	name: "toggle-left-panel",
	title: () => (store.studioLayout.showLeftPanel ? "Hide Left Panel" : "Show Left Panel"),
	icon: () => (store.studioLayout.showLeftPanel ? "lucide-panel-left-close" : "lucide-panel-left-open"),
	group: "View",
	keys: { combo: "Mod+Shift+Backslash", description: "Toggle Left Panel" },
	action: () => (store.studioLayout.showLeftPanel = !store.studioLayout.showLeftPanel),
})

commands.register({
	name: "toggle-right-panel",
	title: () => (store.studioLayout.showRightPanel ? "Hide Right Panel" : "Show Right Panel"),
	icon: () => (store.studioLayout.showRightPanel ? "lucide-panel-right-close" : "lucide-panel-right-open"),
	group: "View",
	action: () => (store.studioLayout.showRightPanel = !store.studioLayout.showRightPanel),
})

// General

commands.register({
	name: "search-blocks",
	title: "Search Blocks",
	icon: "lucide-search",
	group: "General",
	keys: { combo: "Mod+Shift+F", description: "Search Blocks" },
	action: () => (store.showSearchBlock = true),
})

commands.register({
	name: "app-settings",
	title: "App Settings",
	icon: "lucide-settings",
	group: "General",
	condition: () => Boolean(store.activeApp),
	action: () => (store.showAppDialog = true),
})

commands.register({
	name: "studio-settings",
	title: "Studio Settings",
	icon: "lucide-sliders-vertical",
	group: "General",
	action: () => (store.showStudioSettingsDialog = true),
})

commands.register({
	name: "shortcuts",
	title: "Keyboard Shortcuts",
	icon: "lucide-command",
	group: "General",
	keys: { combo: "Shift+Slash", description: "Show Keyboard Shortcuts" },
	action: () => (store.showShortcutsDialog = true),
})
