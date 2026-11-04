<template>
	<div>
		<!-- row metrics and typography mirror ThoughtStep exactly: when this block
		     merges into a tool group it swaps components without moving a pixel -->
		<button
			class="group flex w-full cursor-pointer items-baseline gap-2.5 py-2 text-left md:py-2.5"
			@click="open = !open"
		>
			<!-- leading slot doubles as the disclosure control (see ToolStep) -->
			<span class="relative h-3.5 w-3.5 flex-none self-center text-ink-gray-5">
				<ThoughtIcon
					class="h-3.5 w-3.5 transition-opacity"
					:class="open ? 'opacity-0' : 'group-hover:opacity-0'"
				/>
				<span
					class="lucide-chevron-right absolute inset-0 size-3.5 transition-[opacity,transform]"
					:class="open ? 'rotate-90 opacity-100' : 'opacity-0 group-hover:opacity-100'"
					aria-hidden="true"
				/>
			</span>
			<span class="flex-none text-base font-medium" :class="live ? 'flow-shimmer' : 'text-ink-gray-9'">{{
				live ? "Thinking" : "Thought"
			}}</span>
		</button>
		<div
			v-if="open"
			class="mt-2 border-l-2 border-outline-gray-2 pl-3 text-base leading-relaxed text-ink-gray-6"
		>
			<span v-if="block.redacted" class="italic">Thinking is encrypted for this model.</span>
			<MarkdownContent v-else :text="block.thinking" />
		</div>
	</div>
</template>

<script setup>

import { usePanelOpen } from "../panels.js"
import MarkdownContent from "./MarkdownContent.vue"
import ThoughtIcon from "./ThoughtIcon.vue"

const props = defineProps({
	id: { type: String, required: true },
	block: { type: Object, required: true },
	live: { type: Boolean, default: false },
})

const open = usePanelOpen(() => props.id)
</script>
