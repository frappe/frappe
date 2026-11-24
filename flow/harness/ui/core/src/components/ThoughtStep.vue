<template>
	<div>
		<component
			:is="expandable ? 'button' : 'div'"
			class="flex w-full items-baseline gap-2.5 py-1.5 text-left"
			:class="expandable ? 'group cursor-pointer' : ''"
			@click="expandable && (open = !open)"
		>
			<!-- as ToolStep: the icon's place doubles as the chevron's -->
			<span class="relative size-3.5 flex-none self-center text-ink-gray-5">
				<ThoughtIcon
					class="h-3.5 w-3.5 transition-opacity"
					:class="open ? 'opacity-0' : expandable ? 'group-hover:opacity-0' : ''"
				/>
				<span
					v-if="expandable"
					class="lucide-chevron-right absolute inset-0 size-3.5 transition-[opacity,transform]"
					:class="open ? 'rotate-90 opacity-100' : 'opacity-0 group-hover:opacity-100'"
					aria-hidden="true"
				/>
			</span>
			<span class="min-w-0 truncate text-base text-ink-gray-6 group-hover:text-ink-gray-8">
				<span :class="live ? 'flow-shimmer' : ''">{{ live ? __("Thinking") : __("Thought") }}</span>
				<!-- no preview of the thought itself: only why one can't be opened -->
				<template v-if="block.redacted">
					<span class="text-ink-gray-4"> · </span>
					<span>{{ __("Thinking is encrypted for this model.") }}</span>
				</template>
			</span>
		</component>

		<!-- as the turn's first thought (ThinkingBlock): a rule at its side, not a box -->
		<div v-if="open && expandable" class="my-1 border-l-2 border-outline-gray-2 pl-3">
			<div ref="panelEl" class="max-h-[260px] overflow-y-auto" @scroll="onPanelScroll">
				<MarkdownContent :text="block.thinking" class="text-base leading-relaxed text-ink-gray-6" />
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue"

import { usePanelOpen } from "../panels.js"
import { __ } from "../translate.js"
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
</script>
