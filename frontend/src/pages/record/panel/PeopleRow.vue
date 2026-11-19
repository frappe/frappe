<!-- One people row, assigned or shared: a label named by an icon, then whatever edits or
     shows the people. Always drawn; an empty row says so instead of vanishing. -->
<template>
	<div class="grid grid-cols-[130px_1fr] items-center gap-2">
		<span class="flex min-w-0 items-center gap-2 truncate text-base text-ink-gray-5">
			<span class="size-4 shrink-0" :class="icon" aria-hidden="true" />
			{{ label }}
		</span>
		<slot />
	</div>
</template>

<script setup lang="ts">
defineProps<{
	label: string;
	/** A lucide class, `lucide-user`. */
	icon: string;
}>();
</script>
