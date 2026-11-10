<script setup>
import { computed } from "vue";

const props = defineProps({
	image: { type: String, default: "" },
	name: { type: String, required: true },
});

const initials = computed(() =>
	props.name
		.split(/\s+/)
		.filter(Boolean)
		.slice(0, 2)
		.map((word) => word[0])
		.join("")
		.toUpperCase()
);
</script>

<template>
	<div
		class="flex size-30 items-center justify-center overflow-hidden rounded-full bg-surface-gray-3 text-5xl-semibold text-ink-gray-7 shadow-sm"
	>
		<img v-if="image" :src="image" :alt="name" class="size-full object-cover" />
		<span v-else>{{ initials }}</span>
	</div>
</template>
