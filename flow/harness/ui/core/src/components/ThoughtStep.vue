<template>
	<div>
		<component
			:is="expandable ? 'button' : 'div'"
			class="flex w-full items-baseline gap-2.5 py-2.5 text-left"
			:class="expandable ? 'group cursor-pointer' : ''"
			@click="expandable && (open = !open)"
		>
			<!-- leading slot doubles as the disclosure control (see ToolStep) -->
			<span class="relative h-3.5 w-3.5 flex-none self-center text-ink-gray-5">
				<ThoughtIcon
					class="h-3.5 w-3.5 transition-opacity"
					:class="open ? 'opacity-0' : expandable ? 'group-hover:opacity-0' : ''"
				/>
				<FeatherIcon
					v-if="expandable"
					name="chevron-right"
					class="absolute inset-0 h-3.5 w-3.5 transition-[opacity,transform]"
					:class="open ? 'rotate-90 opacity-100' : 'opacity-0 group-hover:opacity-100'"
				/>
			</span>
			<span class="flex-none text-sm font-medium" :class="live ? 'flow-shimmer' : 'text-ink-gray-9'">{{
				live ? "Thinking" : "Thought"
			}}</span>
			<span class="min-w-0 flex-1 truncate text-sm text-ink-gray-5 group-hover:text-ink-gray-7">{{ preview }}</span>
		</component>

		<div
			v-if="open && expandable"
			class="mb-1.5 mt-1 rounded-[10px] border border-outline-gray-1 bg-surface-base px-3.5 py-3"
		>
			<div ref="panelEl" class="max-h-[260px] overflow-y-auto" @scroll="onPanelScroll">
				<MarkdownContent :text="block.thinking" class="text-sm leading-relaxed text-ink-gray-6" />
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { usePanelOpen } from "../panels.js"
import MarkdownContent from "./MarkdownContent.vue"
import ThoughtIcon from "./ThoughtIcon.vue"

const props = defineProps({
	id: { type: String, required: true },
	block: { type: Object, required: true },
	// this thought's chunks are still streaming in
	live: { type: Boolean, default: false },
})

const open = usePanelOpen(() => props.id)

// The open panel follows streamed text like the thread does: pinned while the
// user is at its bottom (trivially true when the content is still short),
// released the moment they scroll up inside it.
const panelEl = ref(null)
let panelPinned = false
const atPanelBottom = (el) => el.scrollHeight - el.scrollTop - el.clientHeight < 8
function onPanelScroll() {
	if (panelEl.value) panelPinned = atPanelBottom(panelEl.value)
}
watch(panelEl, (el) => {
	if (!el) return
	panelPinned = atPanelBottom(el)
	// opening near the bottom edge would reveal the panel off-screen; nudge it in
	el.parentElement.scrollIntoView({ block: "nearest", behavior: "smooth" })
})
watch(
	() => props.block.thinking,
	async () => {
		if (!panelPinned) return
		await nextTick()
		const el = panelEl.value
		if (el) el.scrollTop = el.scrollHeight
	},
)

const expandable = computed(() => !props.block.redacted && !!props.block.thinking)
const preview = computed(() => {
	if (props.block.redacted) return "Thinking is encrypted for this model."
	const text = props.block.thinking ?? ""
	const line = text.split("\n").find((l) => l.trim()) ?? ""
	// markdown syntax is noise at one-line preview size; the panel renders it fully
	return line
		.replace(/^#{1,6}\s+/, "")
		.replace(/\*\*([^*]+)\*\*/g, "$1")
		.replace(/__([^_]+)__/g, "$1")
		.replace(/\*([^*]+)\*/g, "$1")
		.replace(/`([^`]+)`/g, "$1")
		.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
})
</script>
