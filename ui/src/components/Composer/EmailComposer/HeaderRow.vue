<template>
	<div class="flex gap-2 py-1.5" :class="itemsCenter ? 'items-center' : 'items-start'">
		<!-- leading-6 = the recipient control's min-h-6, so the label centers on the
		     first line of chips regardless of how many lines they wrap to; bottom-px
		     mirrors the chip text's own mb-0.5 raise. -->
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
