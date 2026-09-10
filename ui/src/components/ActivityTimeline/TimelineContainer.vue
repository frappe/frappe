<template>
	<div
		class="grid h-full min-h-0 flex-1 grid-rows-[minmax(0,1fr)]"
		:class="{
			'[mask-image:linear-gradient(to_bottom,transparent,black_12px,black_calc(100%-12px),transparent)]':
				fade,
		}"
	>
		<slot />
	</div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ fade?: boolean }>(), { fade: true });
</script>
