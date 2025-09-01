<template>
	<div class="overflow-hidden" :class="[sizeClasses, shapeClasses]">
		<img
			v-if="image && !imgFetchError"
			:src="image"
			:alt="alt"
			class="h-full w-full object-cover"
			@error="(err) => handleImageError(err)"
		/>
		<div
			v-else
			class="border-ink-gray-3 flex h-full w-full select-none items-center justify-center border-2 border-dashed bg-surface-gray-1 uppercase text-ink-gray-5"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import type { ImageViewProps } from "@/types/studio_components/ImageView"

const props = withDefaults(defineProps<ImageViewProps>(), {
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

const imgFetchError = ref()
function handleImageError(err: any) {
	if (err.type) {
		imgFetchError.value = true
	}
}
</script>
