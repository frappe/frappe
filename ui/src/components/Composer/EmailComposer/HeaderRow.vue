<template>
	<div class="flex gap-2 py-1.5" :class="itemsCenter ? 'items-center' : 'items-start'">
		<span
			class="shrink-0 text-p-sm text-ink-gray-4"
			:class="itemsCenter ? '' : 'relative bottom-px leading-6'"
			>{{ label }}</span
		>
		<slot />
	</div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ label: string; itemsCenter?: boolean }>(), {
	itemsCenter: false,
});
</script>
