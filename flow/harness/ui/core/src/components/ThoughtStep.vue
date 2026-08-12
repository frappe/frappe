<template>
	<div>
		<component
			:is="expandable ? 'button' : 'div'"
			class="flex w-full items-baseline gap-2.5 px-3 py-2 text-left"
			:class="expandable ? 'cursor-pointer hover:bg-surface-gray-2' : ''"
			@click="expandable && (open = !open)"
		>
			<span class="flex-none text-xs font-medium text-ink-gray-9">Thought</span>
			<span class="min-w-0 flex-1 truncate text-xs text-ink-gray-5">{{ preview }}</span>
			<FeatherIcon
				v-if="expandable"
				name="chevron-right"
				class="h-[13px] w-[13px] flex-none self-center text-ink-gray-4 transition-transform"
				:class="open ? 'rotate-90' : ''"
			/>
		</component>

		<div v-if="open" ref="panelEl" class="border-t border-outline-gray-1 bg-surface-white px-3 py-2.5">
			<MarkdownContent
				:text="block.thinking"
				class="max-h-[260px] overflow-y-auto text-xs leading-relaxed text-ink-gray-6"
			/>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue"
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue"

import MarkdownContent from "./MarkdownContent.vue"

const props = defineProps({ block: { type: Object, required: true } })

const open = ref(false)
const panelEl = ref(null)
watch(open, (value) => {
	if (value) nextTick(() => panelEl.value?.scrollIntoView({ block: "nearest", behavior: "smooth" }))
})

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
