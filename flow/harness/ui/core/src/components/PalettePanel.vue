<!-- The shared dropdown shell for everything that floats above the composer:
     slash commands, model picker, thinking, providers. Overlay + panel +
     header; the composer's own text is the search. -->
<template>
	<div class="fixed inset-0 z-10" @click="emit('close')" />
	<section
		ref="panel"
		tabindex="-1"
		:aria-label="title"
		class="flow-palette-panel absolute bottom-[calc(100%+4px)] left-0 z-20 flex max-h-[min(352px,72vh)] w-full flex-col overflow-hidden rounded-8 py-1 border border-outline-gray-1 bg-surface-base shadow-[0_6px_20px_rgba(0,0,0,0.05)] outline-none"
		@pointermove="onPointerMove"
	>
		<!-- a slim bar only for a page's way back and controls, in the list's heading style;
		     a root list labels itself -->
		<header v-if="back || $slots.actions" class="mt-1 flex h-8 flex-none items-center gap-1 px-2.5">
			<button
				v-if="back"
				class="grid h-6 w-6 place-items-center rounded-full text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-8"
				title="Back"
				@click="emit('back')"
			>
				<FeatherIcon name="arrow-left" class="h-3.5 w-3.5" />
			</button>
			<span class="min-w-0 truncate text-2xs font-medium text-ink-gray-5" :class="back ? '' : 'pl-1'">
				{{ title }}
			</span>
			<span class="flex-1" />
			<slot name="actions" />
		</header>
		<slot />
	</section>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { nextNavigationIndex } from "../paletteNav.js"

const props = defineProps({
	title: { type: String, required: true },
	back: { type: Boolean, default: false },
	// the search the rows answer: a new one hands the highlight to its top row
	query: { type: String, default: "" },
	// the rows don't answer the search yet: an Enter waits for the ones that do
	busy: { type: Boolean, default: false },
})
const emit = defineEmits(["close", "back"])
const panel = ref(null)
let activeItem = null
let observer = null
let enterWaits = false
let topWaits = false

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

// a search's top row takes the highlight, or the current row (aria-current) with none typed
function highlightTop() {
	topWaits = false
	const rows = items()
	setActive((props.query ? null : rows.find((row) => row.getAttribute("aria-current") === "true")) ?? rows[0] ?? null)
	activeItem?.scrollIntoView?.({ block: "nearest" })
}

// Only a moving pointer takes the highlight: rows the keyboard scrolls under a resting
// pointer get a pointerover, or in some browsers a move to the same spot.
let pointerAt = ""
function onPointerMove(event) {
	const at = `${event.clientX},${event.clientY}`
	if (at === pointerAt) return
	pointerAt = at
	const item = event.target.closest?.("[data-palette-item]:not(:disabled)")
	if (item && panel.value?.contains(item)) setActive(item)
}

// Capture at window level so palettes work whether focus lives in their panel or in
// the composer textarea, whose text is their search.
function onKey(event) {
	// an IME's Enter picks its candidate, not a row
	if (event.isComposing || event.keyCode === 229) return
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
	} else if (event.key === "Enter" && (activeItem || props.busy)) {
		event.preventDefault()
		event.stopPropagation()
		if (props.busy) enterWaits = true
		else activeItem.click()
	}
}

// a search's rows may trail it (busy): the top row and a waiting Enter wait for them
watch(
	() => props.query,
	() => {
		if (props.busy) topWaits = true
		else nextTick(highlightTop)
	},
)
watch(
	() => props.busy,
	(busy) => {
		if (busy || !(enterWaits || topWaits)) return
		const enter = enterWaits
		enterWaits = false
		nextTick(() => {
			if (topWaits) highlightTop()
			else syncItems()
			if (enter) activeItem?.click()
		})
	},
)

onMounted(async () => {
	window.addEventListener("keydown", onKey, true)
	observer = new MutationObserver(syncItems)
	observer.observe(panel.value, { childList: true, subtree: true })
	await nextTick()
	syncItems()
})
onBeforeUnmount(() => {
	window.removeEventListener("keydown", onKey, true)
	observer?.disconnect()
})
</script>

<style scoped>
.flow-palette-panel :deep([data-palette-item][data-palette-active="true"]) {
	background: var(--surface-gray-2);
	color: var(--ink-gray-9);
}
.flow-palette-panel :deep([data-palette-active="true"] .flow-palette-hint) {
	color: var(--ink-gray-5);
}
</style>
