<template>
	<div>
		<button
			class="flex items-center gap-1.5 text-sm text-ink-gray-5 hover:text-ink-gray-8"
			@click="open = !open"
		>
			<span :class="live ? 'flow-shimmer font-medium' : ''">{{ live ? "Thinking" : "Thought" }}</span>
			<FeatherIcon
				name="chevron-right"
				class="h-3.5 w-3.5 transition-transform"
				:class="open ? 'rotate-90' : ''"
			/>
		</button>
		<div
			v-if="open"
			ref="panelEl"
			class="mt-2 border-l-2 border-outline-gray-2 pl-3 text-sm leading-relaxed text-ink-gray-6"
		>
			<span v-if="block.redacted" class="italic">Thinking is encrypted for this model.</span>
			<MarkdownContent v-else :text="block.thinking" />
		</div>
	</div>
</template>

<script setup>
import { nextTick, ref, watch } from "vue"
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue"

import MarkdownContent from "./MarkdownContent.vue"

defineProps({
	block: { type: Object, required: true },
	live: { type: Boolean, default: false },
})

const open = ref(false)
const panelEl = ref(null)
watch(open, (value) => {
	if (value) nextTick(() => panelEl.value?.scrollIntoView({ block: "nearest", behavior: "smooth" }))
})
</script>
