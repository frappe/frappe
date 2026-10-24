<!-- The shared dropdown shell for everything that floats above the composer:
     slash commands, model picker, thinking, providers. Overlay + panel +
     header; the composer's own text is the search. A `dropdown` hangs from
     a toolbar button instead, the model and approval mode buttons' own
     lists, moved along to stay on the page. -->
<template>
	<div class="fixed inset-0 z-10" @click="emit('close')" />
	<section
		ref="panel"
		:aria-label="title"
		class="flow-palette-panel absolute z-20 flex flex-col overflow-hidden rounded-8 border border-outline-gray-1 flow-composer-surface shadow-[0_6px_20px_rgba(0,0,0,0.05)]"
		:class="
			dropdown
				? ['flow-dropdown bottom-[calc(100%+8px)] w-[var(--dropdown-width)]', align === 'right' ? 'right-0' : 'left-0']
				: 'bottom-[calc(100%+4px)] left-0 w-full'
		"
		:style="{
			maxHeight: `${cap}px`,
			height: full ? `${cap}px` : undefined,
			'--dropdown-width': dropdown ? `min(${width}px, 100vw - 16px)` : undefined,
			translate: shift ? `${shift}px` : undefined,
		}"
		@mousedown="keepFocus"
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
	// the rows are still loading: the panel holds its full height, so it doesn't open short and jump
	full: { type: Boolean, default: false },
	// hung from a toolbar button, not spread over the composer: lined up with its `align` edge,
	// `width` wide, or the page's width less 8px a side
	dropdown: { type: Boolean, default: false },
	align: { type: String, default: "right" },
	width: { type: Number, default: 304 },
})
const emit = defineEmits(["close", "back"])
const panel = ref(null)
// 352px tall at most, and no taller than the room above it, 8px short of the page's top: a
// phone's keyboard can leave less
const cap = ref(352)
// a dropdown whose button sits near the page's side moves along, to stay 8px inside it
const shift = ref(0)
let activeItem = null
let observer = null
let sizer = null
let enterWaits = false
let topWaits = false

function fit() {
	const rect = panel.value.getBoundingClientRect()
	cap.value = Math.min(352, Math.floor(rect.bottom) - 8)
	if (!props.dropdown) return
	const left = rect.left - shift.value
	const room = document.documentElement.clientWidth - 8 - (rect.right - shift.value)
	shift.value = Math.round(Math.max(8 - left, Math.min(0, room)))
}

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

// a click on the panel leaves the focus in the composer, whose text is the search; a form
// field (a provider's key) still takes it
function keepFocus(event) {
	if (!event.target.closest("input, textarea, select")) event.preventDefault()
}

// Only a moving pointer takes the highlight: rows the keyboard scrolls under a resting
// pointer get a pointerover, or in some browsers a move to the same spot. A finger scrolls.
let pointerAt = ""
function onPointerMove(event) {
	if (event.pointerType === "touch") return
	const at = `${event.clientX},${event.clientY}`
	if (at === pointerAt) return
	pointerAt = at
	const item = event.target.closest?.("[data-palette-item]:not(:disabled)")
	if (item && panel.value?.contains(item)) setActive(item)
}

// Capture at window level so palettes work whether focus lives in their panel or in
// the composer textarea, whose text is their search.
function onKey(event) {
	// put away with a view the host hides (inert), it answers no keys
	if (panel.value?.closest("[inert]")) return
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
	// refitted as the page (the keyboard) or what it hangs from (a growing composer) resizes
	if (typeof ResizeObserver !== "undefined") {
		fit()
		sizer = new ResizeObserver(fit)
		sizer.observe(document.documentElement)
		if (panel.value.offsetParent) sizer.observe(panel.value.offsetParent)
	}
	await nextTick()
	syncItems()
	// a list opens on its current row, however far down it sits, clear of the bottom fade
	activeItem?.scrollIntoView?.({ block: "center" })
})
onBeforeUnmount(() => {
	window.removeEventListener("keydown", onKey, true)
	observer?.disconnect()
	sizer?.disconnect()
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
/* a dark dropdown over the composer is half a step lighter than the box (flow.css): its highlight
   steps up with it */
[data-theme="dark"] .flow-palette-panel.flow-dropdown :deep([data-palette-item][data-palette-active="true"]) {
	background: color-mix(in srgb, var(--surface-gray-2) 50%, var(--surface-gray-3));
}
</style>
