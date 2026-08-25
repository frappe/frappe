<template>
	<div>
		<button
			class="group flex items-center gap-2.5 text-sm text-ink-gray-5 hover:text-ink-gray-8"
			@click="open = !open"
		>
			<!-- leading slot doubles as the disclosure control (see ToolStep) -->
			<span class="relative h-3.5 w-3.5 flex-none">
				<ThoughtIcon
					class="h-3.5 w-3.5 transition-opacity"
					:class="open ? 'opacity-0' : 'group-hover:opacity-0'"
				/>
				<FeatherIcon
					name="chevron-right"
					class="absolute inset-0 h-3.5 w-3.5 transition-[opacity,transform]"
					:class="open ? 'rotate-90 opacity-100' : 'opacity-0 group-hover:opacity-100'"
				/>
			</span>
			<span :class="live ? 'flow-shimmer font-medium' : ''">{{ live ? "Thinking" : "Thought" }}</span>
		</button>
		<div
			v-if="open"
			class="mt-2 border-l-2 border-outline-gray-2 pl-3 text-sm leading-relaxed text-ink-gray-6"
		>
			<span v-if="block.redacted" class="italic">Thinking is encrypted for this model.</span>
			<MarkdownContent v-else :text="block.thinking" />
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue"
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue"

import MarkdownContent from "./MarkdownContent.vue"
import ThoughtIcon from "./ThoughtIcon.vue"

defineProps({
	block: { type: Object, required: true },
	live: { type: Boolean, default: false },
})

const open = ref(false)
</script>
