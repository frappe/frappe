<template>
	<div class="overflow-hidden shadow-lg" :class="[sizeClasses, shapeClasses]">
		<img :src="image" :alt="alt" class="h-full w-full object-cover" />
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"

interface ImageProps {
	image?: string
	alt?: string
	size?: "xs" | "sm" | "md" | "lg"
	shape?: "circle" | "square"
}

const props = withDefaults(defineProps<ImageProps>(), {
	size: "lg",
	shape: "square",
})

const shapeClasses = computed(() => {
	return {
		circle: "rounded-full",
		square: {
			xs: "rounded-[4px]",
			sm: "rounded-[5px]",
			md: "rounded-[5px]",
			lg: "rounded-[6px]",
		}[props.size],
	}[props.shape]
})

const sizeClasses = computed(() => {
	return {
		xs: "h-32 w-32",
		sm: "h-48 w-48",
		md: "h-64 w-64",
		lg: "h-96 w-96",
	}[props.size]
})
</script>
