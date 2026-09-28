import router from "@/router/studio_router"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import blockController from "@/utils/blockController"
import { openInDesk } from "@/utils/helpers"
import { nextTick } from "vue"
import type { LeftPanelOptions } from "@/types"

/** A key binding for a command. The description labels it in the shortcuts dialog. */
export type CommandKeys = {
	/** a frappe-ui combo such as "Mod+Shift+K" */
	combo: string
	allowInInput?: boolean
	description: string
}

export type Command = {
	name: string
	/** a function when the label depends on state, such as Show or Hide Left Panel */
	title: string | (() => string)
	icon: string | (() => string)
	group: CommandGroup
	action: () => void
	condition?: () => boolean
	keys?: CommandKeys
	/** keep the palette open, for a command that opens a step */
	keepOpen?: boolean
	/** false for a key binding that should not be listed in the palette */
	inPalette?: boolean
}

export const commandGroups = ["Navigate", "Page", "Panels", "Layers", "View", "General", "Edit"] as const
export type CommandGroup = (typeof commandGroups)[number]

export const resolveText = (value: string | (() => string)) => (typeof value === "function" ? value() : value)

// the page route chunk imports this after pinia is installed, so the lookups resolve
const store = useStudioStore()
const canvasStore = useCanvasStore()

const commands: Command[] = []

/** registering a name again replaces the command, so a remounted component does not duplicate it */
export function registerCommand(command: Command) {
	const index = commands.findIndex((existing) => existing.name === command.name)
	if (index === -1) commands.push(command)
	else commands[index] = command
}

export function getCommands() {
	return commands.filter((command) => command.condition?.() ?? true)
}

/**
 * Every command that declares a binding, shaped for useKeyboardShortcut. Read once at
 * setup, so a command registered later gets no binding until the next reload.
 */
export function commandShortcuts() {
	return commands
		.filter((command) => command.keys)
		.map((command) => ({
			...command.keys!,
			group: command.group,
			enabled: command.condition,
			handler: () => command.action(),
		}))
}

// Navigate

registerCommand({
	name: "go-to-dashboard",
	title: "Go to Dashboard",
	icon: "lucide-layout-dashboard",
	group: "Navigate",
	action: () => router.push({ name: "Home" }),
})

registerCommand({
	name: "view-in-desk",
	title: "View App in Desk",
	icon: "lucide-arrow-up-right",
	group: "Navigate",
	condition: () => Boolean(store.activeApp),
	action: () => openInDesk(store.activeApp!),
})

// Page

registerCommand({
	name: "preview-page",
	title: "Preview Page",
	icon: "lucide-play",
	group: "Page",
	condition: () => Boolean(store.activeApp && store.activePage),
	action: () => store.openPageInBrowser(store.activeApp!, store.activePage!, true),
})

registerCommand({
	name: "publish-page",
	title: "Publish Page",
	icon: "lucide-globe",
	group: "Page",
	// like the publish button: a fragment has to be saved or closed first
	condition: () => Boolean(store.activePage) && !canvasStore.showFragmentCanvas,
	action: () => store.publishPage(),
})

registerCommand({
	name: "page-options",
	title: "Page Options",
	icon: "lucide-file-cog",
	group: "Page",
	condition: () => Boolean(store.activePage),
	action: () => (store.showPageOptions = true),
})

// Panels

const leftPanelTabs: { tab: LeftPanelOptions; icon: string }[] = [
	{ tab: "Pages", icon: "lucide-book" },
	{ tab: "Add Component", icon: "lucide-plus-circle" },
	{ tab: "Layers", icon: "lucide-layers" },
	{ tab: "Data", icon: "lucide-database" },
	{ tab: "Code", icon: "lucide-code" },
	{ tab: "AI Assistant", icon: "lucide-sparkle" },
]

for (const { tab, icon } of leftPanelTabs) {
	registerCommand({
		name: `open-${tab.toLowerCase().replace(/ /g, "-")}-panel`,
		title: `Open ${tab}`,
		icon,
		group: "Panels",
		action: () => {
			store.studioLayout.showLeftPanel = true
			store.studioLayout.leftPanelActiveTab = tab
		},
	})
}

// Layers

const showLayersTab = async () => {
	store.studioLayout.showLeftPanel = true
	store.studioLayout.leftPanelActiveTab = "Layers"
	await nextTick()
}

registerCommand({
	name: "expand-layers",
	title: "Expand All Layers",
	icon: "lucide-chevrons-up-down",
	group: "Layers",
	action: async () => {
		await showLayersTab()
		store.activeLayers?.expandAll()
	},
})

registerCommand({
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

registerCommand({
	name: "toggle-left-panel",
	title: () => (store.studioLayout.showLeftPanel ? "Hide Left Panel" : "Show Left Panel"),
	icon: () => (store.studioLayout.showLeftPanel ? "lucide-panel-left-close" : "lucide-panel-left-open"),
	group: "View",
	keys: { combo: "Mod+Shift+Backslash", description: "Toggle Left Panel" },
	action: () => (store.studioLayout.showLeftPanel = !store.studioLayout.showLeftPanel),
})

registerCommand({
	name: "toggle-right-panel",
	title: () => (store.studioLayout.showRightPanel ? "Hide Right Panel" : "Show Right Panel"),
	icon: () => (store.studioLayout.showRightPanel ? "lucide-panel-right-close" : "lucide-panel-right-open"),
	group: "View",
	action: () => (store.studioLayout.showRightPanel = !store.studioLayout.showRightPanel),
})

registerCommand({
	name: "toggle-panels",
	title: "Toggle Panels",
	icon: "lucide-panels-left-bottom",
	group: "View",
	inPalette: false,
	keys: { combo: "Mod+Backslash", description: "Toggle Panels" },
	action: () => {
		store.studioLayout.showRightPanel = !store.studioLayout.showRightPanel
		store.studioLayout.showLeftPanel = store.studioLayout.showRightPanel
	},
})

registerCommand({
	name: "fit-canvas",
	title: "Fit Canvas to Screen",
	icon: "lucide-maximize",
	group: "View",
	keys: { combo: "Mod+Shift+Digit0", description: "Fit Canvas to Screen" },
	action: () => canvasStore.activeCanvas?.setScaleAndTranslate(),
})

// General

registerCommand({
	name: "search-blocks",
	title: "Search Blocks",
	icon: "lucide-search",
	group: "General",
	keys: { combo: "Mod+Shift+F", description: "Search Blocks" },
	action: () => (store.showSearchBlock = true),
})

registerCommand({
	name: "app-settings",
	title: "App Settings",
	icon: "lucide-settings",
	group: "General",
	condition: () => Boolean(store.activeApp),
	action: () => (store.showAppDialog = true),
})

registerCommand({
	name: "studio-settings",
	title: "Studio Settings",
	icon: "lucide-sliders-vertical",
	group: "General",
	action: () => (store.showStudioSettingsDialog = true),
})

registerCommand({
	name: "shortcuts",
	title: "Keyboard Shortcuts",
	icon: "lucide-command",
	group: "General",
	keys: { combo: "Shift+Slash", description: "Show Keyboard Shortcuts" },
	action: () => (store.showShortcutsDialog = true),
})

// Edit: key bindings with no palette entry

registerCommand({
	name: "select-mode",
	title: "Select Mode",
	icon: "lucide-mouse-pointer",
	group: "Edit",
	inPalette: false,
	keys: { combo: "V", description: "Select Mode" },
	action: () => (store.mode = "select"),
})

registerCommand({
	name: "container-mode",
	title: "Container Mode",
	icon: "lucide-square",
	group: "Edit",
	inPalette: false,
	keys: { combo: "C", description: "Container Mode" },
	action: () => (store.mode = "container"),
})

registerCommand({
	name: "duplicate-block",
	title: "Duplicate Block",
	icon: "lucide-copy",
	group: "Edit",
	inPalette: false,
	keys: { combo: "Mod+D", description: "Duplicate Block" },
	action: () => {
		if (!blockController.isAnyBlockSelected() || blockController.multipleBlocksSelected()) return
		blockController.getSelectedBlocks()[0].duplicateBlock()
	},
})

registerCommand({
	name: "undo",
	title: "Undo",
	icon: "lucide-undo-2",
	group: "Edit",
	inPalette: false,
	keys: { combo: "Mod+Z", description: "Undo" },
	action: () => {
		const history = canvasStore.activeCanvas?.history
		if (history?.canUndo()) history.undo()
	},
})

registerCommand({
	name: "redo",
	title: "Redo",
	icon: "lucide-redo-2",
	group: "Edit",
	inPalette: false,
	keys: { combo: "Mod+Shift+Z", description: "Redo" },
	action: () => {
		const history = canvasStore.activeCanvas?.history
		if (history?.canRedo()) history.redo()
	},
})
