<template>
	<!-- the control sits beside the title and description; in a narrow frame beside the title only,
	     so the description has the row's width -->
	<div class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 py-4 md:gap-x-8">
		<div class="flex min-w-0 items-center gap-2">
			<span class="text-sm font-medium text-ink-gray-9">{{ title }}</span>
			<SavedNote v-if="saved !== undefined" :value="saved" class="ml-auto" />
		</div>
		<div :class="description && 'md:row-span-2'"><slot /></div>
		<p v-if="description" class="col-span-2 mt-1.5 text-xs leading-5 text-ink-gray-6 md:col-span-1">{{ description }}</p>
	</div>
</template>

<script setup>
import SavedNote from "./SavedNote.vue"

// One setting: a title and description on the left, its control on the right. A setting that
// applies as it changes passes its value as `saved`: "Saved" shows at the end of the title's line,
// where it takes no room from the description.
defineProps({
	title: { type: String, required: true },
	description: { type: String, default: "" },
	saved: { type: [String, Number], default: undefined },
})
</script>
