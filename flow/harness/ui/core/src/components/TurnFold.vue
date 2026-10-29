<template>
	<div class="border-b border-outline-gray-1 pb-2 pt-1">
		<button
			type="button"
			class="flex select-none items-center gap-1.5 hover:text-ink-gray-8"
			:class="[layout.phone ? 'text-base' : 'text-sm md:text-base', expanded ? 'font-medium text-ink-gray-8' : 'text-ink-gray-5']"
			:aria-expanded="expanded"
			@click="$emit('toggle')"
		>
			<span>{{ label }}</span>
			<span
				class="lucide-chevron-right mt-px size-3.5 flex-none transition-transform"
				:class="expanded ? 'rotate-90' : ''"
				aria-hidden="true"
			/>
		</button>
	</div>
</template>

<script setup>
import { layout } from "../layout.js"

defineProps({
	label: { type: String, required: true },
	expanded: { type: Boolean, default: false },
})

defineEmits(["toggle"])
</script>
