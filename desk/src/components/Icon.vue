<template>
	<svg :aria-label="name" class="fill-transparent stroke-current">
		<use :href="`#${name}`" />
	</svg>
</template>

<script setup>
const props = defineProps({
	name: {
		type: String,
		required: true,
	},
})
</script>
