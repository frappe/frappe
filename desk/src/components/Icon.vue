<template>
	<svg :aria-label="name" class="fill-transparent stroke-current">
		<use :href="iconName" />
	</svg>
</template>

<script setup>
import { computed } from "vue"

const props = defineProps({
	name: {
		type: String,
		required: true,
	},
})

const iconName = computed(() => {
	const isEspresso = props.name.startsWith("es-")
	return isEspresso ? `#${props.name}` : `#icon-${props.name}`
})
</script>
