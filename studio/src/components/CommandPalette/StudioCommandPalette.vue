<template>
	<CommandPalette
		v-model:show="show"
		v-model:searchQuery="searchQuery"
		:groups="paletteGroups"
		:step-label="activeStep?.label"
		:placeholder="activeStep?.placeholder"
		:hint="activeStep?.hint"
		@select="executeCommand"
		@back="handleBack"
	/>
</template>

<script setup lang="ts">
import { computed, ref, watch, type ComputedRef } from "vue"
import { useRouter } from "vue-router"
import { useKeyboardShortcut } from "frappe-ui"

import CommandPalette from "@/components/CommandPalette/CommandPalette.vue"
import CommandPaletteItem from "@/components/CommandPalette/CommandPaletteItem.vue"
import type { CommandPaletteItem as CPItem } from "@/components/CommandPalette/CommandPalette.vue"
import { commandGroups, commands, resolveText } from "@/components/Commands"
import useStudioStore from "@/stores/studioStore"
import useComponentEditorStore from "@/stores/componentEditorStore"
import useCanvasStore from "@/stores/canvasStore"
import { studioComponents } from "@/data/studioComponents"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type { StudioComponent } from "@/types/Studio/StudioComponent"

type PaletteItem = CPItem & { action?: () => void; group?: string; shortcutName?: string }
type Step = { id: string; label: string; placeholder: string; hint: string }

const store = useStudioStore()
const canvasStore = useCanvasStore()
const router = useRouter()

const show = ref(false)
const searchQuery = ref("")
const activeStep = ref<Step | null>(null)

useKeyboardShortcut({
	combo: "Mod+K",
	description: "Open Command Palette",
	group: "General",
	allowInInput: true,
	handler: () => (show.value = true),
})

// a reopened palette starts at the root, not the step it closed on
watch(show, (open) => !open && handleBack())

const openStep = (step: Step) => {
	activeStep.value = step
	searchQuery.value = ""
}

// the step commands stay here: they drive activeStep, which is local
commands.register({
	name: "go-to-page",
	title: "Go to Page",
	icon: "lucide-file-search",
	group: "Navigate",
	after: "go-to-dashboard",
	keepOpen: true,
	action: () =>
		openStep({
			id: "go-to-page",
			label: "Go to Page",
			placeholder: "Search by title or route...",
			hint: "This app has no other pages",
		}),
})

commands.register({
	name: "go-to-component",
	title: "Go to Component",
	icon: "lucide-box",
	group: "Navigate",
	after: "go-to-page",
	keepOpen: true,
	action: () =>
		openStep({
			id: "go-to-component",
			label: "Go to Component",
			placeholder: "Search components...",
			hint: "There are no Studio components yet",
		}),
})

const paletteCommands = computed<PaletteItem[]>(() =>
	commands.visible.value
		.filter((command) => command.inPalette !== false)
		.map((command) => ({
			name: command.name,
			title: resolveText(command.title),
			icon: resolveText(command.icon),
			description: command.group,
			group: command.group,
			// the name the shortcuts dialog lists it under, e.g. "Toggle Panels"
			shortcutName: command.keys?.description,
			keepOpen: command.keepOpen,
			action: command.action,
		})),
)

const RECENT_COMMANDS_KEY = "studio:recent_commands"

function getRecentCommandNames(): string[] {
	try {
		return JSON.parse(localStorage.getItem(RECENT_COMMANDS_KEY) || "[]")
	} catch {
		return []
	}
}

const recentCommandNames = ref<string[]>(getRecentCommandNames())

function trackRecentCommand(name: string) {
	recentCommandNames.value = [name, ...recentCommandNames.value.filter((n) => n !== name)].slice(0, 5)
	try {
		localStorage.setItem(RECENT_COMMANDS_KEY, JSON.stringify(recentCommandNames.value))
	} catch {
		// storage is a convenience; the palette works without it
	}
}

const recentCommands = computed(
	() =>
		recentCommandNames.value
			.map((name) => paletteCommands.value.find((command) => command.name === name))
			.filter(Boolean) as PaletteItem[],
)

const byRecency = (a: PaletteItem, b: PaletteItem) => {
	const ai = recentCommandNames.value.indexOf(a.name)
	const bi = recentCommandNames.value.indexOf(b.name)
	return (ai === -1 ? Infinity : ai) - (bi === -1 ? Infinity : bi)
}

const pageItems = computed<PaletteItem[]>(() =>
	Object.values(store.appPages)
		.filter((page: StudioPage) => page.name !== store.activePage?.name)
		.map((page: StudioPage) => ({
			name: `page-${page.name}`,
			title: page.page_title || page.name,
			description: page.route || "/",
			icon: "lucide-file",
			action: () =>
				router.push({ name: "StudioPage", params: { appID: store.activeApp?.name, pageID: page.name } }),
		})),
)

const componentItems = computed<PaletteItem[]>(() => {
	// Do not list a component that is open. A second editor can overwrite its edits.
	const openIds = new Set(canvasStore.fragmentStack.map((fragment) => fragment.fragmentId))
	return (studioComponents.data || [])
		.filter((component: StudioComponent) => !openIds.has(component.component_id))
		.map((component: StudioComponent) => ({
			name: `component-${component.component_id}`,
			title: component.component_name,
			icon: "lucide-box",
			action: () => useComponentEditorStore().editComponent(component.component_id),
		}))
})

const stepItems: Record<string, ComputedRef<PaletteItem[]>> = {
	"go-to-page": pageItems,
	"go-to-component": componentItems,
}

const matches = (item: PaletteItem, query: string) =>
	[item.title, item.description, item.shortcutName].some((text) => text?.toLowerCase().includes(query))

const paletteGroups = computed(() => {
	const query = searchQuery.value.toLowerCase().trim()

	if (activeStep.value) {
		const all = stepItems[activeStep.value.id].value
		const items = query ? all.filter((item) => matches(item, query)) : all
		return items.length
			? [{ title: activeStep.value.label, hideTitle: true, showDescription: true, component: CommandPaletteItem, items }]
			: []
	}

	if (query) {
		const items = paletteCommands.value.filter((item) => matches(item, query)).sort(byRecency)
		return items.length
			? [{ title: "Commands", hideTitle: true, showDescription: true, component: CommandPaletteItem, items }]
			: []
	}

	const grouped = commandGroups
		.map((group) => ({
			title: group as string,
			component: CommandPaletteItem,
			items: paletteCommands.value.filter((command) => command.group === group),
		}))
		.filter((group) => group.items.length)

	if (!recentCommands.value.length) return grouped
	return [
		{ title: "Recent", showDescription: true, component: CommandPaletteItem, items: recentCommands.value },
		...grouped,
	]
})

function executeCommand(item: CPItem) {
	// pages and components picked inside a step are not commands
	if (!activeStep.value) {
		trackRecentCommand(item.name)
	}
	;(item as PaletteItem).action?.()
}

function handleBack() {
	activeStep.value = null
	searchQuery.value = ""
}
</script>
