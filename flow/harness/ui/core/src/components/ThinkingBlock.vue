<template>
	<div>
		<!-- row metrics and typography mirror ThoughtStep exactly: when this block
		     merges into a tool group it swaps components without moving a pixel -->
		<button class="group flex w-full cursor-pointer items-baseline gap-2.5 py-2 text-left md:py-2.5" @click="open = !open">
			<ThoughtIcon class="h-3.5 w-3.5 flex-none self-center text-ink-gray-5" />
			<span class="text-base text-ink-gray-6 group-hover:text-ink-gray-8" :class="live ? 'flow-shimmer' : ''">{{
				live ? __("Thinking") : __("Thought")
			}}</span>
			<span
				class="lucide-chevron-down size-3.5 flex-none self-center text-ink-gray-5 transition-[opacity,transform]"
				:class="open ? 'rotate-180' : 'opacity-0 group-hover:opacity-100'"
				aria-hidden="true"
			/>
		</button>
		<div
			v-if="open"
			class="mt-2 border-l-2 border-outline-gray-2 pl-3 text-base leading-relaxed text-ink-gray-6"
		>
			<span v-if="block.redacted" class="italic">{{ __("Thinking is encrypted for this model.") }}</span>
			<MarkdownContent v-else :text="block.thinking" />
		</div>
	</div>
</template>

<script setup>

import { usePanelOpen } from "../panels.js"
import { __ } from "../translate.js"
import MarkdownContent from "./MarkdownContent.vue"
import ThoughtIcon from "./ThoughtIcon.vue"

const props = defineProps({
	id: { type: String, required: true },
	block: { type: Object, required: true },
	live: { type: Boolean, default: false },
})

const open = usePanelOpen(() => props.id)
</script>
