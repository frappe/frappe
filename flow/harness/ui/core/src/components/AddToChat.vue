<template>
	<!-- a layer over the thread, up to the composer; only the pill itself takes clicks -->
	<div ref="layer" class="pointer-events-none absolute inset-x-0 top-0 z-10" :style="{ bottom: composerHeight + 'px' }">
		<button
			v-if="pill"
			type="button"
			class="flow-add-to-chat pointer-events-auto absolute"
			:style="{
				left: pill.x + 'px',
				top: pill.y + 'px',
				transform: pill.below ? 'translate(-50%, 8px)' : 'translate(-50%, calc(-100% - 8px))',
			}"
			@mousedown.prevent
			@click="add"
		>
			Add to chat
		</button>
	</div>
</template>

<script setup>
import { inject, onBeforeUnmount, onMounted, ref } from "vue"

// Floating "Add to chat" pill over a text selection inside `within`: queues the
// selected text as a quote for the composer.
const props = defineProps({ within: { type: Object, default: null } })
const flow = inject("flow")
const composerHeight = inject("composerHeight", ref(0))
const layer = ref(null)
const pill = ref(null)
let timer = null

// the selection, when it is a non-empty one inside the thread
function selected() {
	const selection = document.getSelection()
	if (!selection?.rangeCount || selection.isCollapsed) return null
	const range = selection.getRangeAt(0)
	if (!props.within?.contains(range.commonAncestorContainer)) return null
	const text = selection.toString().trim()
	return text ? { range, text } : null
}

// centered above the selection's visible part; under it when there is no room
// above, and never past the layer's bottom (the composer sits there)
function place() {
	const found = selected()
	if (!found) return (pill.value = null)
	const box = layer.value.getBoundingClientRect()
	const rect = found.range.getBoundingClientRect()
	const top = Math.max(rect.top, box.top)
	const bottom = Math.min(rect.bottom, box.bottom)
	if (bottom <= top) return (pill.value = null) // scrolled out of view
	const below = top - box.top < 40
	pill.value = {
		text: found.text,
		x: Math.min(Math.max(rect.left + rect.width / 2, box.left + 60), box.right - 60) - box.left,
		y: (below ? Math.min(bottom, box.bottom - 30) : top) - box.top,
		below,
	}
}

// a collapsing selection hides the pill at once; a growing one settles first
function onSelectionChange() {
	clearTimeout(timer)
	if (!selected()) return (pill.value = null)
	timer = setTimeout(place, 150)
}

function add() {
	flow.addQuote(pill.value.text)
	document.getSelection()?.removeAllRanges()
	pill.value = null
}

onMounted(() => {
	document.addEventListener("selectionchange", onSelectionChange)
	document.addEventListener("scroll", place, true) // the pill rides along, and returns with its selection
})
onBeforeUnmount(() => {
	clearTimeout(timer)
	document.removeEventListener("selectionchange", onSelectionChange)
	document.removeEventListener("scroll", place, true)
})
</script>
