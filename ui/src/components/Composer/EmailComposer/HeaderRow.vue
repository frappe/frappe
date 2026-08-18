<template>
	<div class="flex gap-2 py-1.5" :class="itemsCenter ? 'items-center' : 'items-start'">
		<span
			class="w-[52px] shrink-0 text-p-sm text-ink-gray-4"
			:class="itemsCenter ? '' : 'mt-1 relative bottom-0.5'"
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
