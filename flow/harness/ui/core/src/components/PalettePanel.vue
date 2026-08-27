<!-- The shared dropdown shell for everything that floats above the composer:
     slash commands, model picker, thinking, providers. Overlay + panel +
     header; search is a slot so each surface stays a thin list. -->
<template>
	<div class="fixed inset-0 z-10" @click="emit('close')" />
	<section
		ref="panel"
		tabindex="-1"
		:aria-label="title"
		class="flow-palette-panel absolute bottom-[calc(100%+10px)] left-0 z-20 flex max-h-[min(500px,72vh)] w-full flex-col overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-base shadow-[0_18px_50px_rgba(0,0,0,0.14)] outline-none"
		@pointerover="onPointerOver"
	>
		<header class="flex h-11 flex-none items-center gap-2 border-b border-outline-gray-1 px-2">
			<button
				v-if="back"
				class="flex h-7 w-7 items-center justify-center rounded-5 text-ink-gray-5 hover:bg-surface-gray-2"
				title="Back"
				@click="emit('back')"
			>
				<FeatherIcon name="arrow-left" class="h-3.5 w-3.5" />
			</button>
			<span class="min-w-0 truncate text-xs font-medium text-ink-gray-9" :class="back ? '' : 'pl-1'">
				{{ title }}
			</span>
			<span class="flex-1" />
			<slot name="actions" />
		</header>
		<slot name="search" />
		<slot />
	</section>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { nextNavigationIndex } from "../paletteNav.js"

const props = defineProps({
	title: { type: String, required: true },
	back: { type: Boolean, default: false },
	autofocus: { type: Boolean, default: true },
})
const emit = defineEmits(["close", "back"])
const panel = ref(null)
let activeItem = null
let observer = null

function items() {
	return [...(panel.value?.querySelectorAll("[data-palette-item]:not(:disabled)") ?? [])]
}

function setActive(item) {
	activeItem?.removeAttribute("data-palette-active")
	activeItem = item
	activeItem?.setAttribute("data-palette-active", "true")
}

function syncItems() {
	const rows = items()
	if (!rows.includes(activeItem)) {
		setActive(rows.find((row) => row.getAttribute("aria-current") === "true") ?? rows[0] ?? null)
	}
}

function onPointerOver(event) {
	const item = event.target.closest?.("[data-palette-item]:not(:disabled)")
	if (item && panel.value?.contains(item)) setActive(item)
}

// Capture at window level so palettes work whether focus lives in their search
// input, their panel, or the composer textarea behind the slash-command list.
function onKey(event) {
	if (event.key === "Escape") {
		event.preventDefault()
		event.stopPropagation()
		emit("close")
		return
	}
	const rows = items()
	const current = rows.indexOf(activeItem)
	const nextIndex = nextNavigationIndex(current, rows.length, event.key)
	if (nextIndex !== null) {
		event.preventDefault()
		event.stopPropagation()
		setActive(rows[nextIndex])
		activeItem.scrollIntoView({ block: "nearest" })
	} else if (event.key === "Enter" && activeItem) {
		event.preventDefault()
		event.stopPropagation()
		activeItem.click()
	}
}

onMounted(async () => {
	window.addEventListener("keydown", onKey, true)
	observer = new MutationObserver(syncItems)
	observer.observe(panel.value, { childList: true, subtree: true })
	await nextTick()
	syncItems()
	// Search palettes focus their input first; list-only palettes focus the panel.
	if (props.autofocus && !panel.value?.contains(document.activeElement)) {
		panel.value?.focus({ preventScroll: true })
	}
})
onBeforeUnmount(() => {
	window.removeEventListener("keydown", onKey, true)
	observer?.disconnect()
})
</script>

<style scoped>
.flow-palette-panel :deep([data-palette-item][data-palette-active="true"]) {
	background: var(--surface-gray-2);
}
</style>
