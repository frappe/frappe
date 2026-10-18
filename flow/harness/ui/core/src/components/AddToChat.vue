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
			<FeatherIcon name="message-square" class="h-3.5 w-3.5 text-ink-gray-6" />
			Add to chat
		</button>
	</div>
</template>

<script setup>
import { inject, onBeforeUnmount, onMounted, ref } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

// Floating "Add to chat" pill over a text selection inside `within`: queues the
// selected text as a quote for the composer.
const props = defineProps({ within: { type: Object, default: null } })
const flow = inject("flow")
const composerHeight = inject("composerHeight", ref(0))
const layer = ref(null)
const pill = ref(null)
let timer = null
let resizeObserver = null

// the selection, when it is a non-empty one inside the thread
function selected() {
	const selection = document.getSelection()
	if (!selection?.rangeCount || selection.isCollapsed) return null
	const range = selection.getRangeAt(0)
	if (!props.within?.contains(range.commonAncestorContainer)) return null
	const text = selection.toString().trim()
	return text ? { range, text } : null
}

// the selection's first (or last) line, measured from its text: the range's own
// boxes cover whole blocks, and split a line at every bold or code run
function edgeLine(range, last) {
	const walker = document.createTreeWalker(props.within, NodeFilter.SHOW_TEXT)
	const step = () => (last ? walker.previousNode() : walker.nextNode())
	let node = last ? range.endContainer : range.startContainer
	while (last && node.lastChild) node = node.lastChild
	walker.currentNode = node
	if (node.nodeType !== Node.TEXT_NODE) node = step()
	while (node && !range.intersectsNode(node)) node = step() // text in the boundary's element, outside the range
	let line = null
	for (; node && range.intersectsNode(node); node = step()) {
		const piece = document.createRange()
		piece.selectNodeContents(node)
		if (node === range.startContainer) piece.setStart(node, range.startOffset)
		if (node === range.endContainer) piece.setEnd(node, range.endOffset)
		const rects = [...piece.getClientRects()].filter((rect) => rect.width && rect.height)
		for (const rect of last ? rects.reverse() : rects) {
			const middle = (rect.top + rect.bottom) / 2
			if (line && (middle < line.top || middle > line.bottom)) return line // the next line
			line ??= { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom }
			line.left = Math.min(line.left, rect.left)
			line.right = Math.max(line.right, rect.right)
		}
	}
	return line
}

// centered above the selection's first line; under its last line when there is
// no room above, and never past the layer's bottom (the composer sits there)
function place() {
	const found = selected()
	if (!found) return (pill.value = null)
	const box = layer.value.getBoundingClientRect()
	const rect = found.range.getBoundingClientRect()
	const top = Math.max(rect.top, box.top)
	const bottom = Math.min(rect.bottom, box.bottom)
	if (bottom <= top) return (pill.value = null) // scrolled out of view
	const first = edgeLine(found.range, false) ?? rect
	const below = first.top - box.top < 40
	const anchor = below ? (edgeLine(found.range, true) ?? rect) : first
	pill.value = {
		text: found.text,
		x: Math.min(Math.max((anchor.left + anchor.right) / 2, box.left + 60), box.right - 60) - box.left,
		y: (below ? Math.min(bottom, box.bottom - 36) : first.top) - box.top,
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
	if (typeof ResizeObserver === "undefined") return
	resizeObserver = new ResizeObserver(place) // a resized thread re-wraps the selection
	resizeObserver.observe(layer.value)
})
onBeforeUnmount(() => {
	clearTimeout(timer)
	resizeObserver?.disconnect()
	document.removeEventListener("selectionchange", onSelectionChange)
	document.removeEventListener("scroll", place, true)
})
</script>
