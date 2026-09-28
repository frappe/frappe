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
import { computed, ref, watch } from "vue"
import { useRouter } from "vue-router"
import { useKeyboardShortcut } from "frappe-ui"

import CommandPalette from "@/components/CommandPalette/CommandPalette.vue"
import CommandPaletteItem from "@/components/CommandPalette/CommandPaletteItem.vue"
import type { CommandPaletteItem as CPItem } from "@/components/CommandPalette/CommandPalette.vue"
import { commandGroups, commands, resolveText } from "@/components/Commands"
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"

type PaletteItem = CPItem & { action?: () => void; group?: string; shortcutName?: string }
type Step = { id: string; label: string; placeholder: string; hint: string }

const store = useStudioStore()
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

// the step command stays here: it drives activeStep, which is local
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

const matches = (item: PaletteItem, query: string) =>
	[item.title, item.description, item.shortcutName].some((text) => text?.toLowerCase().includes(query))

const paletteGroups = computed(() => {
	const query = searchQuery.value.toLowerCase().trim()

	if (activeStep.value?.id === "go-to-page") {
		const items = query ? pageItems.value.filter((item) => matches(item, query)) : pageItems.value
		return items.length
			? [{ title: "Pages", hideTitle: true, showDescription: true, component: CommandPaletteItem, items }]
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
	if (!item.name.startsWith("page-")) {
		trackRecentCommand(item.name)
	}
	;(item as PaletteItem).action?.()
}

function handleBack() {
	activeStep.value = null
	searchQuery.value = ""
}
</script>
