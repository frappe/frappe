<template>
	<div class="border-b border-outline-gray-1 pb-2 pt-1">
		<button
			type="button"
			class="flex select-none items-center gap-1.5 text-sm hover:text-ink-gray-8"
			:class="expanded ? 'font-medium text-ink-gray-8' : 'text-ink-gray-5'"
			:aria-expanded="expanded"
			@click="$emit('toggle')"
		>
			<span>{{ label }}</span>
			<FeatherIcon
				name="chevron-right"
				class="mt-px h-3.5 w-3.5 flex-none transition-transform"
				:class="expanded ? 'rotate-90' : ''"
			/>
		</button>
	</div>
</template>

<script setup>
import FeatherIcon from "./FeatherIcon.vue"

defineProps({
	label: { type: String, required: true },
	expanded: { type: Boolean, default: false },
})

defineEmits(["toggle"])
</script>
