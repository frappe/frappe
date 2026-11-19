<!-- A small group inside a Settings section: a heading in the Editor panel's section style and a
     divider above it. -->
<template>
	<div
		class="border-t border-outline-gray-1 pb-1 pt-3 first:border-t-0 first:pt-0"
		:data-settings-group="label"
	>
		<h3 class="flex h-7 items-center text-base font-medium text-ink-gray-9">{{ label }}</h3>
		<slot />
	</div>
</template>

<script setup lang="ts">
defineProps<{ label: string }>();
</script>
